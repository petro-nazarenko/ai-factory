"""Google Sheets integration using gspread."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, cast

import gspread
from google.oauth2.service_account import Credentials
from gspread import Spreadsheet, Worksheet
from gspread.exceptions import SpreadsheetNotFound

from src.integrations.base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfig,
    IntegrationConnectionError,
)
from src.utils.logger import get_logger
from src.utils.retry import with_retry

logger = get_logger(__name__)


@dataclass
class GoogleSheetsConfig(IntegrationConfig):
    """Configuration for Google Sheets integration."""

    credentials_path: Path = field(
        default_factory=lambda: Path.home() / ".config" / "upwork-learn" / "credentials.json"
    )
    spreadsheet_id: str | None = None


@dataclass
class CellRange:
    """Represents a cell range in a sheet."""

    sheet_name: str
    start_row: int
    end_row: int
    start_col: int
    end_col: int

    def to_a1_notation(self) -> str:
        """Convert to A1 notation."""
        start = gspread.utils.rowcol_to_a1(self.start_row, self.start_col)
        end = gspread.utils.rowcol_to_a1(self.end_row, self.end_col)
        return f"{self.sheet_name}!{start}:{end}"


@dataclass
class WriteOptions:
    """Options for write operations."""

    raw: bool = True
    major_dimension: str = "ROWS"


class GoogleSheetsClient(BaseIntegration):
    """Client for Google Sheets API operations.

    Provides methods for reading, writing, and manipulating Google Sheets data.
    Supports batch operations and caching for improved performance.
    """

    _config: GoogleSheetsConfig
    SCOPES: ClassVar[list[str]] = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(
        self,
        config: GoogleSheetsConfig | None = None,
        spreadsheet_id: str | None = None,
    ) -> None:
        super().__init__(config)
        self._config = config or GoogleSheetsConfig()
        self._spreadsheet_id = spreadsheet_id or self._config.spreadsheet_id
        self._client: gspread.Client | None = None
        self._spreadsheet: Spreadsheet | None = None
        self._metadata_cache: dict[str, Any] = {}

    @property
    def service_name(self) -> str:
        return "google-sheets"

    def connect(self) -> None:
        """Authenticate and connect to Google Sheets API."""
        try:
            credentials = self._load_credentials()
            self._client = gspread.authorize(credentials)
            self._connected = True
            self._logger.info("Connected to Google Sheets API")
        except FileNotFoundError as e:
            raise AuthenticationError(f"Credentials file not found: {e}") from e
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to connect: {e}") from e

    def disconnect(self) -> None:
        """Close the connection."""
        self._client = None
        self._spreadsheet = None
        self._metadata_cache = {}
        self._connected = False
        self._logger.info("Disconnected from Google Sheets API")

    def _load_credentials(self) -> Any:
        """Load credentials from JSON env var or file.

        Checks ``GOOGLE_SHEETS_CREDENTIALS_JSON`` first (base64-encoded JSON),
        then falls back to the file at ``credentials_path``.
        """
        json_b64 = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON")
        if json_b64:
            info = json.loads(base64.b64decode(json_b64).decode())
            return Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                info,
                scopes=self.SCOPES,
            )

        cred_path = self._config.credentials_path
        if not cred_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {cred_path}")
        return Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            str(cred_path),
            scopes=self.SCOPES,
        )

    def open_spreadsheet(self, spreadsheet_id: str | None = None) -> Spreadsheet:
        """Open a spreadsheet by ID.

        Args:
            spreadsheet_id: Spreadsheet ID. Uses default if not provided.

        Returns:
            Spreadsheet object

        Raises:
            SpreadsheetNotFound: If spreadsheet doesn't exist
        """
        spreadsheet_id = spreadsheet_id or self._spreadsheet_id
        if not spreadsheet_id:
            raise ValueError("No spreadsheet_id provided")

        try:
            if not self._client:
                self.connect()

            if not self._client:
                raise IntegrationConnectionError("Google Sheets client is not initialized")

            self._spreadsheet = self._client.open_by_key(spreadsheet_id)
            self._spreadsheet_id = spreadsheet_id
            self._logger.info(
                "Opened spreadsheet",
                spreadsheet_id=spreadsheet_id,
                title=self._spreadsheet.title,
            )
            return self._spreadsheet
        except (AuthenticationError, IntegrationConnectionError, ValueError):
            raise
        except SpreadsheetNotFound:
            raise
        except gspread.exceptions.APIError as e:
            raise IntegrationConnectionError(f"Google Sheets API error: {e}") from e
        except Exception as e:
            raise IntegrationConnectionError(
                f"Failed to open spreadsheet {spreadsheet_id}: {e}"
            ) from e

    @with_retry(max_attempts=3)
    def read_range(
        self,
        range_name: str,
        spreadsheet_id: str | None = None,
        value_render: str = "FORMATTED_VALUE",
    ) -> list[list[str | int | float]]:
        """Read a range of cells from a sheet.

        Args:
            range_name: Range in A1 notation (e.g., "Sheet1!A1:C10")
            spreadsheet_id: Optional spreadsheet ID
            value_render: How to render values ("FORMATTED_VALUE", "FORMULA", "UNFORMATTED_VALUE")

        Returns:
            2D list of cell values
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        try:
            values = spreadsheet.values_get(
                range_name,
                params={"valueRenderOption": value_render},
            )
            result = values.get("values", [])
            self._logger.info(
                "Read range",
                range=range_name,
                rows=len(result),
            )
            return cast(list[list[str | int | float]], result)
        except Exception as e:
            self._logger.error("Failed to read range", range=range_name, error=str(e))
            raise

    @with_retry(max_attempts=3)
    def write_range(
        self,
        range_name: str,
        values: list[list[Any]],
        spreadsheet_id: str | None = None,
        options: WriteOptions | None = None,
    ) -> dict[str, Any]:
        """Write values to a range in a sheet.

        Args:
            range_name: Range in A1 notation
            values: 2D list of values to write
            spreadsheet_id: Optional spreadsheet ID
            options: Write options

        Returns:
            API response
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        options = options or WriteOptions()

        try:
            data = {
                "range": range_name,
                "majorDimension": options.major_dimension,
                "values": values,
            }
            result = spreadsheet.values_update(
                range_name,
                params={
                    "valueInputOption": "RAW" if options.raw else "USER_ENTERED",
                },
                body=data,
            )
            self._logger.info(
                "Wrote range",
                range=range_name,
                rows=len(values),
            )
            return cast(dict[str, Any], result)
        except Exception as e:
            self._logger.error("Failed to write range", range=range_name, error=str(e))
            raise

    def append_row(
        self,
        values: list[Any],
        sheet_name: str = "Sheet1",
        spreadsheet_id: str | None = None,
    ) -> dict[str, Any]:
        """Append a row to a sheet.

        Args:
            values: List of values to append
            sheet_name: Name of the sheet
            spreadsheet_id: Optional spreadsheet ID

        Returns:
            API response
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            result = worksheet.append_row(values)
            self._logger.info(
                "Appended row",
                sheet=sheet_name,
                values=values[:3],
            )
            return dict(result)
        except Exception as e:
            self._logger.error("Failed to append row", sheet=sheet_name, error=str(e))
            raise

    def update_cell(
        self,
        row: int,
        col: int,
        value: Any,
        sheet_name: str = "Sheet1",
        spreadsheet_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a single cell.

        Args:
            row: Row number (1-indexed)
            col: Column number (1-indexed)
            value: Value to set
            sheet_name: Name of the sheet
            spreadsheet_id: Optional spreadsheet ID

        Returns:
            API response
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            cell = gspread.utils.rowcol_to_a1(row, col)
            result = worksheet.update(cell, value)
            self._logger.info(
                "Updated cell",
                cell=cell,
                value=value,
            )
            return dict(result)
        except Exception as e:
            self._logger.error("Failed to update cell", cell=f"{row}:{col}", error=str(e))
            raise

    @with_retry(max_attempts=3)
    def batch_write(
        self,
        data: list[dict[str, Any]],
        spreadsheet_id: str | None = None,
    ) -> dict[str, Any]:
        """Batch write multiple ranges.

        Args:
            data: List of {"range": "...", "values": [[...]]} dicts
            spreadsheet_id: Optional spreadsheet ID

        Returns:
            API response
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        body = {"valueInputOption": "USER_ENTERED", "data": data}

        try:
            result = spreadsheet.values_batch_update(body=body)
            self._logger.info(
                "Batch write",
                ranges=len(data),
            )
            return cast(dict[str, Any], result)
        except Exception as e:
            self._logger.error("Batch write failed", error=str(e))
            raise

    def get_worksheets(self, spreadsheet_id: str | None = None) -> list[str]:
        """Get list of worksheet names.

        Args:
            spreadsheet_id: Optional spreadsheet ID

        Returns:
            List of worksheet names
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        return [ws.title for ws in spreadsheet.worksheets()]

    def create_worksheet(
        self,
        title: str,
        rows: int = 100,
        cols: int = 26,
        spreadsheet_id: str | None = None,
    ) -> Worksheet:
        """Create a new worksheet.

        Args:
            title: Worksheet title
            rows: Number of rows
            cols: Number of columns
            spreadsheet_id: Optional spreadsheet ID

        Returns:
            Created worksheet
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        try:
            worksheet = spreadsheet.add_worksheet(title, rows, cols)
            self._logger.info("Created worksheet", title=title)
            return worksheet
        except Exception as e:
            self._logger.error("Failed to create worksheet", title=title, error=str(e))
            raise

    def delete_worksheet(
        self,
        title: str,
        spreadsheet_id: str | None = None,
    ) -> None:
        """Delete a worksheet.

        Args:
            title: Worksheet title
            spreadsheet_id: Optional spreadsheet ID
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(title)
            spreadsheet.del_worksheet(worksheet)
            self._logger.info("Deleted worksheet", title=title)
        except Exception as e:
            self._logger.error("Failed to delete worksheet", title=title, error=str(e))
            raise

    def _get_or_open_spreadsheet(self, spreadsheet_id: str | None) -> Spreadsheet:
        """Get current or open new spreadsheet."""
        sid = spreadsheet_id or self._spreadsheet_id
        if self._spreadsheet and (sid is None or sid == self._spreadsheet_id):
            return self._spreadsheet
        return self.open_spreadsheet(sid)

    def clear_sheet(
        self,
        sheet_name: str = "Sheet1",
        spreadsheet_id: str | None = None,
    ) -> None:
        """Clear all data from a sheet.

        Args:
            sheet_name: Name of the sheet
            spreadsheet_id: Optional spreadsheet ID
        """
        spreadsheet = self._get_or_open_spreadsheet(spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
            self._logger.info("Cleared sheet", sheet=sheet_name)
        except Exception as e:
            self._logger.error("Failed to clear sheet", sheet=sheet_name, error=str(e))
            raise
