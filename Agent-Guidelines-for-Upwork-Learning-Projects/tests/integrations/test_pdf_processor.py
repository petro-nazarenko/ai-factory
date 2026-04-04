"""Tests for PDF processor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.pdf_processor import (
    PDFConfig,
    PDFMetadata,
    PDFProcessor,
    TableData,
)


class TestPDFConfig:
    """Tests for PDF configuration."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = PDFConfig()
        assert config.max_retries == 3
        assert config.timeout == 30.0
        assert config.password is None

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = PDFConfig(password="secret", max_retries=5)
        assert config.password == "secret"
        assert config.max_retries == 5


class TestPDFMetadata:
    """Tests for PDF metadata dataclass."""

    def test_metadata_creation(self) -> None:
        """Test creating metadata."""
        metadata = PDFMetadata(
            title="Test Document",
            author="Test Author",
            page_count=10,
            encrypted=False,
        )
        assert metadata.title == "Test Document"
        assert metadata.author == "Test Author"
        assert metadata.page_count == 10
        assert metadata.encrypted is False


class TestTableData:
    """Tests for table data extraction."""

    def test_as_dicts(self) -> None:
        """Test converting table to dictionaries."""
        table = TableData(
            page=0,
            table_index=0,
            rows=[
                ["Name", "Age", "City"],
                ["John", "30", "NYC"],
                ["Jane", "25", "LA"],
            ],
            bbox=(0, 0, 100, 100),
        )

        dicts = table.as_dicts

        assert len(dicts) == 2
        assert dicts[0]["Name"] == "John"
        assert dicts[0]["Age"] == "30"
        assert dicts[1]["Name"] == "Jane"

    def test_as_dicts_single_row(self) -> None:
        """Test empty result for single row."""
        table = TableData(
            page=0,
            table_index=0,
            rows=[["Header"]],
            bbox=None,
        )

        dicts = table.as_dicts

        assert len(dicts) == 0

    def test_to_csv_rows(self) -> None:
        """Test CSV generation."""
        table = TableData(
            page=0,
            table_index=0,
            rows=[
                ["A", "B", "C"],
                ["1", "2", "3"],
            ],
            bbox=None,
        )

        csv_content = "".join(list(table.to_csv_rows()))

        assert "A,B,C" in csv_content
        assert "1,2,3" in csv_content


class TestPDFProcessor:
    """Tests for PDF processor."""

    @pytest.fixture
    def processor(self) -> PDFProcessor:
        """Create test processor."""
        return PDFProcessor()

    def test_service_name(self, processor: PDFProcessor) -> None:
        """Test service name property."""
        assert processor.service_name == "pdf-processor"

    def test_initial_state(self, processor: PDFProcessor) -> None:
        """Test initial processor state."""
        assert processor._connected is False
        assert processor._pdf is None

    def test_connect(self, processor: PDFProcessor) -> None:
        """Test connect sets connected state."""
        processor.connect()
        assert processor._connected is True

    def test_disconnect(self, processor: PDFProcessor) -> None:
        """Test disconnect clears state."""
        processor._connected = True
        processor.disconnect()
        assert processor._connected is False
        assert processor._pdf is None

    def test_context_manager(self) -> None:
        """Test context manager usage."""
        processor = PDFProcessor()
        with processor as p:
            assert p._connected is True
        assert processor._connected is False

    def test_open_nonexistent_file(self, processor: PDFProcessor) -> None:
        """Test opening nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            processor.open("nonexistent.pdf")

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_open_pdf(self, mock_pdfplumber: MagicMock, processor: PDFProcessor) -> None:
        """Test opening a PDF file."""
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(), MagicMock()]
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            pdf = processor.open("test.pdf")

        assert pdf is mock_pdf
        assert processor._pdf is mock_pdf
        assert processor._current_path == Path("test.pdf")

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_get_metadata(self, mock_pdfplumber: MagicMock, processor: PDFProcessor) -> None:
        """Test extracting metadata."""
        mock_pdf = MagicMock()
        mock_pdf.metadata = {
            "Title": "Test Doc",
            "Author": "Test Author",
        }
        mock_pdf.pages = [MagicMock()] * 5
        mock_pdf.is_encrypted = False
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            processor.open("test.pdf")
            metadata = processor.get_metadata()

        assert metadata.title == "Test Doc"
        assert metadata.author == "Test Author"
        assert metadata.page_count == 5
        assert metadata.encrypted is False

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_extract_text(self, mock_pdfplumber: MagicMock, processor: PDFProcessor) -> None:
        """Test extracting text."""
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 text"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            processor.open("test.pdf")
            result = processor.extract_text()

        assert result == {0: "Page 1 text", 1: "Page 2 text"}

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_extract_text_specific_pages(
        self, mock_pdfplumber: MagicMock, processor: PDFProcessor
    ) -> None:
        """Test extracting text from specific pages."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page, MagicMock(), MagicMock()]
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            processor.open("test.pdf")
            result = processor.extract_text(page_numbers=[0])

        assert 0 in result
        assert 1 not in result

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_extract_tables(self, mock_pdfplumber: MagicMock, processor: PDFProcessor) -> None:
        """Test extracting tables."""
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["A", "B"], ["1", "2"]],
            [["C", "D"], ["3", "4"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            processor.open("test.pdf")
            tables = processor.extract_tables()

        assert len(tables) == 2
        assert tables[0].page == 0
        assert tables[0].table_index == 0

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_extract_by_keyword(self, mock_pdfplumber: MagicMock, processor: PDFProcessor) -> None:
        """Test extracting text by keyword."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is a test document with TEST keyword."

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            processor.open("test.pdf")
            matches = processor.extract_by_keyword("test")

        assert len(matches) == 2
        assert matches[0]["keyword"].lower() == "test"

    @patch("src.integrations.pdf_processor.pdfplumber")
    def test_extract_invoice_data(
        self, mock_pdfplumber: MagicMock, processor: PDFProcessor
    ) -> None:
        """Test extracting invoice data."""
        invoice_text = """
        Invoice #INV-2024-001
        Date: 01-15-2024
        Total: €150.00
        BTW: €25.00
        """

        mock_page = MagicMock()
        mock_page.extract_text.return_value = invoice_text
        mock_page.extract_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value = mock_pdf

        with patch("pathlib.Path.exists", return_value=True):
            processor.open("test.pdf")
            data = processor.extract_invoice_data("test.pdf")

        assert data["invoice_number"] == "INV-2024-001"
        assert data["date"] == "01-15-2024"
        assert data["total"] == "150.00"

    def test_get_pdf_no_file_open(self, processor: PDFProcessor) -> None:
        """Test error when no PDF is open."""
        with pytest.raises(ValueError, match="No PDF file is currently open"):
            processor._get_pdf(None)
