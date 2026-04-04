"""PDF processing using pdfplumber."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from pdfplumber.pdf import PDF

from src.integrations.base import BaseIntegration, IntegrationConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PDFConfig(IntegrationConfig):
    """Configuration for PDF processing."""

    password: str | None = None


@dataclass
class PDFMetadata:
    """PDF document metadata."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    page_count: int = 0
    encrypted: bool = False


@dataclass
class TableData:
    """Extracted table data."""

    page: int
    table_index: int
    rows: list[list[str | None]]
    bbox: tuple[float, float, float, float] | None

    @property
    def as_dicts(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries.

        Assumes first row is headers.
        """
        if len(self.rows) < 2:
            return []

        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(self.rows[0])]
        result = []
        for row in self.rows[1:]:
            result.append(
                {headers[i]: (str(cell).strip() if cell else None) for i, cell in enumerate(row)}
            )
        return result

    def to_csv_rows(self) -> list[str]:
        """Generate CSV rows."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        for row in self.rows:
            writer.writerow(row)
        return output.getvalue().splitlines()


class PDFProcessor(BaseIntegration):
    """Processor for PDF documents.

    Provides methods for extracting text, tables, and metadata from PDFs.
    Supports multi-page documents and table detection.
    """

    _config: PDFConfig

    def __init__(self, config: PDFConfig | None = None) -> None:
        super().__init__(config)
        self._config = config or PDFConfig()
        self._pdf: PDF | None = None
        self._current_path: Path | None = None

    @property
    def service_name(self) -> str:
        return "pdf-processor"

    def connect(self) -> None:
        """Mark as connected (no external connection needed)."""
        self._connected = True
        self._logger.info("PDF processor initialized")

    def disconnect(self) -> None:
        """Close current PDF if open."""
        self._pdf = None
        self._current_path = None
        self._connected = False

    def open(self, path: str | Path) -> PDF:
        """Open a PDF file.

        Args:
            path: Path to PDF file

        Returns:
            PDF object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not a valid PDF
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        try:
            self._pdf = pdfplumber.open(
                path,
                password=self._config.password,
            )
            self._current_path = path
            self._logger.info(
                "Opened PDF",
                path=str(path),
                pages=len(self._pdf.pages),
            )
            return self._pdf
        except Exception as e:
            raise ValueError(f"Failed to open PDF: {e}") from e

    def close(self) -> None:
        """Close the current PDF."""
        if self._pdf:
            self._pdf.close()
            self._pdf = None
            self._logger.info("Closed PDF")

    def __enter__(self) -> PDFProcessor:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
        self.disconnect()

    def get_metadata(self, path: str | Path | None = None) -> PDFMetadata:
        """Extract metadata from PDF.

        Args:
            path: Path to PDF. Uses currently open PDF if not provided.

        Returns:
            PDF metadata
        """
        pdf = self._get_pdf(path)

        metadata = pdf.metadata or {}
        return PDFMetadata(
            title=metadata.get("Title"),
            author=metadata.get("Author"),
            subject=metadata.get("Subject"),
            creator=metadata.get("Creator"),
            producer=metadata.get("Producer"),
            creation_date=metadata.get("CreationDate"),
            modification_date=metadata.get("ModDate"),
            page_count=len(pdf.pages),
            encrypted=bool(metadata.get("/Encrypt") or metadata.get("Encrypt")),
        )

    def extract_text(
        self,
        page_numbers: list[int] | None = None,
        path: str | Path | None = None,
    ) -> dict[int, str]:
        """Extract text from PDF pages.

        Args:
            page_numbers: Specific page numbers (0-indexed). All pages if None.
            path: Path to PDF. Uses currently open PDF if not provided.

        Returns:
            Dict mapping page number to extracted text
        """
        pdf = self._get_pdf(path)
        pages = page_numbers if page_numbers is not None else range(len(pdf.pages))

        result = {}
        for i in pages:
            if i < 0 or i >= len(pdf.pages):
                raise IndexError(f"Page {i} out of range (0-{len(pdf.pages) - 1})")

            page = pdf.pages[i]
            text = page.extract_text() or ""
            result[i] = text
            self._logger.debug("Extracted text", page=i, chars=len(text))

        self._logger.info("Extracted text", pages=len(result))
        return result

    def extract_all_text(self, path: str | Path | None = None) -> str:
        """Extract all text from PDF as single string.

        Args:
            path: Path to PDF

        Returns:
            Concatenated text from all pages
        """
        text_dict = self.extract_text(path=path)
        return "\n\n".join(f"--- Page {i + 1} ---\n{text}" for i, text in text_dict.items())

    def extract_tables(
        self,
        page_numbers: list[int] | None = None,
        path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> list[TableData]:
        """Extract tables from PDF.

        Args:
            page_numbers: Specific page numbers (0-indexed). All pages if None.
            path: Path to PDF
            settings: Table extraction settings

        Returns:
            List of extracted tables
        """
        pdf = self._get_pdf(path)
        default_settings = {
            "vertical_strategy": "lines_strict",
            "horizontal_strategy": "lines_strict",
            "intersection_tolerance": 5,
        }
        settings = {**default_settings, **(settings or {})}

        pages = page_numbers if page_numbers is not None else range(len(pdf.pages))
        tables: list[TableData] = []

        for i in pages:
            if i < 0 or i >= len(pdf.pages):
                raise IndexError(f"Page {i} out of range")

            page = pdf.pages[i]
            page_tables = page.extract_tables(table_settings=settings)

            for idx, table in enumerate(page_tables):
                tables.append(
                    TableData(
                        page=i,
                        table_index=idx,
                        rows=table,
                        bbox=None,
                    )
                )
                self._logger.debug(
                    "Extracted table",
                    page=i,
                    table=idx,
                    rows=len(table),
                )

        self._logger.info("Extracted tables", total=len(tables))
        return tables

    def extract_tables_as_dicts(
        self,
        page_numbers: list[int] | None = None,
        path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Extract tables and convert to list of dictionaries.

        Args:
            page_numbers: Specific page numbers
            path: Path to PDF

        Returns:
            List of dictionaries representing table rows
        """
        tables = self.extract_tables(page_numbers=page_numbers, path=path)
        result = []
        for table in tables:
            result.extend(table.as_dicts)
        return result

    def extract_by_keyword(
        self,
        keyword: str,
        context_chars: int = 200,
        path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Extract text containing a keyword with surrounding context.

        Args:
            keyword: Keyword to search for
            context_chars: Number of characters to include around match
            path: Path to PDF

        Returns:
            List of matches with context
        """
        text_dict = self.extract_text(path=path)
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        matches = []

        for page_num, text in text_dict.items():
            for match in pattern.finditer(text):
                start = max(0, match.start() - context_chars)
                end = min(len(text), match.end() + context_chars)
                context = text[start:end]

                matches.append(
                    {
                        "page": page_num,
                        "keyword": match.group(),
                        "position": match.start(),
                        "context": context,
                    }
                )

        self._logger.info("Keyword search", keyword=keyword, matches=len(matches))
        return matches

    def extract_invoice_data(self, path: str | Path) -> dict[str, Any]:
        """Extract common invoice fields from PDF.

        Args:
            path: Path to PDF

        Returns:
            Dictionary with extracted invoice data
        """
        text = self.extract_all_text(path=path)

        invoice_patterns = {
            "invoice_number": r"(?:Invoice|Factuur)\s*[:#]?\s*([A-Z0-9-]+)",
            "date": r"(?:Date|Datum)\s*[:#]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            "total": r"(?:Total|Bedrag)\s*[:#]?\s*€?\s*([\d.,]+)",
            "vat": r"(?:VAT|BTW)\s*[:#]?\s*€?\s*([\d.,]+)",
        }

        result = {}
        for field, pattern in invoice_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result[field] = match.group(1).strip()

        tables = self.extract_tables(path=path)
        if tables:
            result["line_items"] = tables[0].as_dicts

        self._logger.info("Extracted invoice data", fields=len(result))
        return result

    def _get_pdf(self, path: str | Path | None) -> PDF:
        """Get currently open PDF or open new one."""
        if self._pdf:
            return self._pdf

        if path:
            return self.open(path)

        raise ValueError("No PDF file is currently open. Provide a path or call open() first.")
