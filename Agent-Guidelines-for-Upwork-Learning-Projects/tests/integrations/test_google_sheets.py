"""Tests for Google Sheets integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.base import AuthenticationError, IntegrationConnectionError
from src.integrations.google_sheets import (
    CellRange,
    GoogleSheetsClient,
    GoogleSheetsConfig,
    WriteOptions,
)


class TestGoogleSheetsConfig:
    """Tests for Google Sheets configuration."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = GoogleSheetsConfig()
        assert config.max_retries == 3
        assert config.timeout == 30.0
        assert config.rate_limit_delay == 1.0
        assert (
            config.credentials_path == Path.home() / ".config" / "upwork-learn" / "credentials.json"
        )

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = GoogleSheetsConfig(
            max_retries=5,
            timeout=60.0,
            credentials_path=Path("/custom/path.json"),
        )
        assert config.max_retries == 5
        assert config.timeout == 60.0
        assert config.credentials_path == Path("/custom/path.json")


class TestWriteOptions:
    """Tests for write options."""

    def test_default_values(self) -> None:
        """Test default write options."""
        options = WriteOptions()
        assert options.raw is True
        assert options.major_dimension == "ROWS"

    def test_custom_values(self) -> None:
        """Test custom write options."""
        options = WriteOptions(raw=False, major_dimension="COLUMNS")
        assert options.raw is False
        assert options.major_dimension == "COLUMNS"


class TestGoogleSheetsClient:
    """Tests for Google Sheets client."""

    @pytest.fixture
    def config(self) -> GoogleSheetsConfig:
        """Create test configuration."""
        return GoogleSheetsConfig(
            credentials_path=Path("tests/fixtures/credentials.json"),
            spreadsheet_id="test_spreadsheet_id",
        )

    @pytest.fixture
    def client(self, config: GoogleSheetsConfig) -> GoogleSheetsClient:
        """Create test client."""
        return GoogleSheetsClient(config=config)

    def test_service_name(self, client: GoogleSheetsClient) -> None:
        """Test service name property."""
        assert client.service_name == "google-sheets"

    def test_initial_state(self, client: GoogleSheetsClient) -> None:
        """Test initial client state."""
        assert client._connected is False
        assert client._spreadsheet is None
        assert client._client is None

    @patch("src.integrations.google_sheets.gspread")
    @patch("src.integrations.google_sheets.Credentials")
    def test_connect_success(
        self, mock_credentials: MagicMock, mock_gspread: MagicMock, client: GoogleSheetsClient
    ) -> None:
        """Test successful connection."""
        mock_creds = MagicMock()
        mock_credentials.from_service_account_file.return_value = mock_creds
        mock_gspread.authorize.return_value = MagicMock()

        client.connect()

        assert client._connected is True
        assert client._client is not None
        mock_gspread.authorize.assert_called_once()

    def test_disconnect(self, client: GoogleSheetsClient) -> None:
        """Test disconnect clears state."""
        client._connected = True
        client._client = MagicMock()
        client._spreadsheet = MagicMock()

        client.disconnect()

        assert client._connected is False
        assert client._client is None
        assert client._spreadsheet is None

    def test_context_manager(self, config: GoogleSheetsConfig) -> None:
        """Test context manager usage."""
        with patch("src.integrations.google_sheets.gspread"):
            with patch("src.integrations.google_sheets.Credentials"):
                client = GoogleSheetsClient(config=config)
                with client:
                    pass

    @patch("src.integrations.google_sheets.gspread")
    def test_read_range(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test reading a range."""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.values_get.return_value = {"values": [["A1", "B1"], ["A2", "B2"]]}
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        result = client.read_range("Sheet1!A1:B2")

        assert result == [["A1", "B1"], ["A2", "B2"]]
        mock_spreadsheet.values_get.assert_called_once()

    @patch("src.integrations.google_sheets.gspread")
    def test_write_range(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test writing to a range."""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.values_update.return_value = {"updatedCells": 4}
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        values = [["X1", "Y1"], ["X2", "Y2"]]
        result = client.write_range("Sheet1!A1:B2", values)

        assert result["updatedCells"] == 4
        mock_spreadsheet.values_update.assert_called_once()

    @patch("src.integrations.google_sheets.gspread")
    def test_append_row(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test appending a row."""
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.append_row.return_value = {"spreadsheetId": "test"}
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        result = client.append_row(["A", "B", "C"])

        assert "spreadsheetId" in result
        mock_worksheet.append_row.assert_called_once_with(["A", "B", "C"])

    @patch("src.integrations.google_sheets.gspread")
    def test_update_cell(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test updating a single cell."""
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.update.return_value = {"updatedCells": 1}
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        result = client.update_cell(row=1, col=1, value="Test")

        assert result["updatedCells"] == 1
        mock_worksheet.update.assert_called_once()

    @patch("src.integrations.google_sheets.gspread")
    def test_get_worksheets(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test getting worksheet names."""
        mock_spreadsheet = MagicMock()
        mock_ws1 = MagicMock()
        mock_ws1.title = "Sheet1"
        mock_ws2 = MagicMock()
        mock_ws2.title = "Sheet2"
        mock_spreadsheet.worksheets.return_value = [mock_ws1, mock_ws2]
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        result = client.get_worksheets()

        assert result == ["Sheet1", "Sheet2"]

    @patch("src.integrations.google_sheets.gspread")
    def test_batch_write(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test batch writing multiple ranges."""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.values_batch_update.return_value = {"totalUpdatedCells": 4}
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        data = [{"range": "Sheet1!A1:B1", "values": [["X", "Y"]]}]
        result = client.batch_write(data)

        assert result["totalUpdatedCells"] == 4
        mock_spreadsheet.values_batch_update.assert_called_once()

    @patch("src.integrations.google_sheets.gspread")
    def test_create_worksheet(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test creating a new worksheet."""
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_spreadsheet.add_worksheet.return_value = mock_ws
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        ws = client.create_worksheet("NewSheet")

        assert ws is mock_ws
        mock_spreadsheet.add_worksheet.assert_called_once_with("NewSheet", 100, 26)

    @patch("src.integrations.google_sheets.gspread")
    def test_delete_worksheet(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test deleting a worksheet."""
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        client.delete_worksheet("OldSheet")

        mock_spreadsheet.del_worksheet.assert_called_once_with(mock_ws)

    @patch("src.integrations.google_sheets.gspread")
    def test_clear_sheet(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test clearing all data from a sheet."""
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        client._client = MagicMock()
        client._spreadsheet = mock_spreadsheet
        client._spreadsheet_id = "test_id"

        client.clear_sheet("Sheet1")

        mock_ws.clear.assert_called_once()

    @patch("src.integrations.google_sheets.Credentials")
    def test_load_credentials_from_env(
        self,
        mock_creds_class: MagicMock,
        client: GoogleSheetsClient,
        monkeypatch: "pytest.MonkeyPatch",
    ) -> None:
        """Test loading credentials from GOOGLE_SHEETS_CREDENTIALS_JSON env var."""
        import base64
        import json

        dummy = {"type": "service_account", "project_id": "test"}
        encoded = base64.b64encode(json.dumps(dummy).encode()).decode()
        monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_JSON", encoded)

        mock_creds_class.from_service_account_info.return_value = MagicMock()
        client._load_credentials()

        mock_creds_class.from_service_account_info.assert_called_once()

    def test_open_spreadsheet_generic_error(self, client: GoogleSheetsClient) -> None:
        """Test open_spreadsheet wraps unexpected errors in IntegrationConnectionError."""
        from src.integrations.base import IntegrationConnectionError

        mock_client = MagicMock()
        mock_client.open_by_key.side_effect = RuntimeError("network failure")
        client._client = mock_client
        client._spreadsheet_id = "test_id"

        with pytest.raises(IntegrationConnectionError):
            client.open_spreadsheet("test_id")


class TestCellRange:
    def test_to_a1_notation(self) -> None:
        cr = CellRange(sheet_name="Sheet1", start_row=1, end_row=3, start_col=1, end_col=3)
        result = cr.to_a1_notation()
        assert result == "Sheet1!A1:C3"


class TestGoogleSheetsConnectErrors:
    @pytest.fixture
    def client(self) -> GoogleSheetsClient:
        config = GoogleSheetsConfig(
            credentials_path=Path("tests/fixtures/credentials.json"),
        )
        return GoogleSheetsClient(config=config)

    def test_connect_file_not_found_raises_authentication_error(
        self, client: GoogleSheetsClient
    ) -> None:
        config = GoogleSheetsConfig(
            credentials_path=Path("/nonexistent/credentials.json"),
        )
        c = GoogleSheetsClient(config=config)
        with pytest.raises(AuthenticationError):
            c.connect()

    def test_connect_generic_error_raises_connection_error(
        self, client: GoogleSheetsClient
    ) -> None:
        with patch("src.integrations.google_sheets.gspread.authorize") as mock_auth:
            mock_auth.side_effect = RuntimeError("API down")
            with pytest.raises(IntegrationConnectionError):
                client.connect()

    def test_open_spreadsheet_no_id_raises_value_error(self, client: GoogleSheetsClient) -> None:
        with pytest.raises(ValueError, match="No spreadsheet_id"):
            client.open_spreadsheet(None)

    def test_open_spreadsheet_spreadsheet_not_found_reraises(
        self, client: GoogleSheetsClient
    ) -> None:
        from gspread.exceptions import SpreadsheetNotFound

        mock_gspread_client = MagicMock()
        mock_gspread_client.open_by_key.side_effect = SpreadsheetNotFound
        client._client = mock_gspread_client

        with pytest.raises(SpreadsheetNotFound):
            client.open_spreadsheet("missing-id")

    def test_open_spreadsheet_api_error_raises_connection_error(
        self, client: GoogleSheetsClient
    ) -> None:
        import gspread

        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": 403, "message": "Forbidden"}}
        mock_response.text = '{"error": {"code": 403, "message": "Forbidden"}}'
        mock_response.status_code = 403
        api_error = gspread.exceptions.APIError(mock_response)

        mock_gspread_client = MagicMock()
        mock_gspread_client.open_by_key.side_effect = api_error
        client._client = mock_gspread_client

        with pytest.raises(IntegrationConnectionError):
            client.open_spreadsheet("sheet-id")


class TestGoogleSheetsMethodErrors:
    """Test that per-method operations propagate errors correctly."""

    @pytest.fixture
    def client_with_mock_spreadsheet(self) -> GoogleSheetsClient:
        config = GoogleSheetsConfig(spreadsheet_id="sid")
        c = GoogleSheetsClient(config=config)
        c._spreadsheet = MagicMock()
        return c

    def test_read_range_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.values_get.side_effect = RuntimeError(  # type: ignore[union-attr]
            "network error"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.read_range("Sheet1!A1:B2")

    def test_write_range_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.values_update.side_effect = RuntimeError(  # type: ignore[union-attr]
            "write failed"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.write_range("Sheet1!A1", [["v"]])

    def test_append_row_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.worksheet.side_effect = RuntimeError(  # type: ignore[union-attr]
            "worksheet missing"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.append_row(["a", "b"])

    def test_batch_write_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.values_batch_update.side_effect = RuntimeError(  # type: ignore[union-attr]
            "batch failed"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.batch_write([{"range": "Sheet1!A1", "values": [["v"]]}])

    def test_create_worksheet_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.add_worksheet.side_effect = RuntimeError(  # type: ignore[union-attr]
            "quota exceeded"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.create_worksheet("NewSheet")

    def test_delete_worksheet_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.worksheet.side_effect = RuntimeError(  # type: ignore[union-attr]
            "not found"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.delete_worksheet("OldSheet")

    def test_clear_sheet_propagates_error(
        self, client_with_mock_spreadsheet: GoogleSheetsClient
    ) -> None:
        client_with_mock_spreadsheet._spreadsheet.worksheet.side_effect = RuntimeError(  # type: ignore[union-attr]
            "sheet missing"
        )
        with pytest.raises(RuntimeError):
            client_with_mock_spreadsheet.clear_sheet("Sheet1")
