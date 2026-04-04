"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


class TestVersionCommand:
    """Tests for version command."""

    def test_version(self) -> None:
        """Test version command outputs version."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "upwork-learn" in result.output


class TestSheetsReadCommand:
    """Tests for sheets-read command."""

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_read_success(self, mock_client_class: MagicMock) -> None:
        """Test successful sheets read."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.read_range.return_value = [["A1", "B1"], ["A2", "B2"]]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-read",
                "--spreadsheet-id",
                "test_id",
                "--range",
                "Sheet1!A1:B2",
            ],
        )

        assert result.exit_code == 0
        mock_client.read_range.assert_called_once_with("Sheet1!A1:B2")

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_read_with_credentials(self, mock_client_class: MagicMock) -> None:
        """Test sheets read with custom credentials path."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.read_range.return_value = []
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-read",
                "--spreadsheet-id",
                "test_id",
                "--range",
                "Sheet1!A1:B2",
                "--credentials",
                "/custom/creds.json",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client_class.call_args
        config = call_kwargs[1]["config"]
        assert config.credentials_path == Path("/custom/creds.json")

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_read_error(self, mock_client_class: MagicMock) -> None:
        """Test sheets read handles errors."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.read_range.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-read",
                "--spreadsheet-id",
                "test_id",
                "--range",
                "Sheet1!A1:B2",
            ],
        )

        assert result.exit_code == 1


class TestSheetsWriteCommand:
    """Tests for sheets-write command."""

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_write_success(self, mock_client_class: MagicMock) -> None:
        """Test successful sheets write."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-write",
                "--spreadsheet-id",
                "test_id",
                "--range",
                "Sheet1!A1:B2",
                "--values",
                '[["A1", "B1"], ["A2", "B2"]]',
            ],
        )

        assert result.exit_code == 0
        mock_client.write_range.assert_called_once()

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_write_invalid_json(self, mock_client_class: MagicMock) -> None:
        """Test sheets write with invalid JSON."""
        result = runner.invoke(
            app,
            [
                "sheets-write",
                "--spreadsheet-id",
                "test_id",
                "--range",
                "Sheet1!A1:B2",
                "--values",
                "not valid json",
            ],
        )

        assert result.exit_code == 1

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_write_with_credentials(self, mock_client_class: MagicMock) -> None:
        """Test sheets write with custom credentials."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-write",
                "--spreadsheet-id",
                "test_id",
                "--range",
                "Sheet1!A1",
                "--values",
                '[["data"]]',
                "--credentials",
                "/path/to/creds.json",
            ],
        )

        assert result.exit_code == 0
        config = mock_client_class.call_args[1]["config"]
        assert config.credentials_path == Path("/path/to/creds.json")


class TestSheetsListCommand:
    """Tests for sheets-list command."""

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_list_success(self, mock_client_class: MagicMock) -> None:
        """Test successful sheets list."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_worksheets.return_value = ["Sheet1", "Sheet2", "Sheet3"]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-list",
                "--spreadsheet-id",
                "test_id",
            ],
        )

        assert result.exit_code == 0
        mock_client.get_worksheets.assert_called_once()

    @patch("src.cli.GoogleSheetsClient")
    def test_sheets_list_error(self, mock_client_class: MagicMock) -> None:
        """Test sheets list handles errors."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_worksheets.side_effect = Exception("Connection error")
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "sheets-list",
                "--spreadsheet-id",
                "test_id",
            ],
        )

        assert result.exit_code == 1


class TestPDFExtractTextCommand:
    """Tests for pdf-extract-text command."""

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_text_success(self, mock_processor_class: MagicMock) -> None:
        """Test successful text extraction."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_text.return_value = {0: "Page 1 text", 1: "Page 2 text"}
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-text", "test.pdf"])

        assert result.exit_code == 0
        mock_processor.extract_text.assert_called_once()

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_text_with_pages(self, mock_processor_class: MagicMock) -> None:
        """Test text extraction with page selection."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_text.return_value = {0: "Page 1 text"}
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-text", "test.pdf", "--pages", "0,1"])

        assert result.exit_code == 0
        mock_processor.extract_text.assert_called_once_with(path="test.pdf", page_numbers=[0, 1])

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_text_to_file(
        self, mock_processor_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test text extraction to output file."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_text.return_value = {0: "Page 1 text"}
        mock_processor_class.return_value = mock_processor

        output_file = str(tmp_path / "output.txt")
        result = runner.invoke(app, ["pdf-extract-text", "test.pdf", "--output", output_file])

        assert result.exit_code == 0
        assert Path(output_file).exists()

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_text_error(self, mock_processor_class: MagicMock) -> None:
        """Test text extraction handles errors."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_text.side_effect = FileNotFoundError("File not found")
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-text", "missing.pdf"])

        assert result.exit_code == 1


class TestPDFExtractTablesCommand:
    """Tests for pdf-extract-tables command."""

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_tables_success(self, mock_processor_class: MagicMock) -> None:
        """Test successful table extraction."""
        from src.integrations.pdf_processor import TableData

        mock_table = MagicMock(spec=TableData)
        mock_table.as_dicts = [{"Name": "John", "Age": "30"}]

        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_tables.return_value = [mock_table]
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-tables", "test.pdf"])

        assert result.exit_code == 0
        mock_processor.extract_tables.assert_called_once_with(path="test.pdf")

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_tables_to_file(
        self, mock_processor_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test table extraction to output file."""
        from src.integrations.pdf_processor import TableData

        mock_table = MagicMock(spec=TableData)
        mock_table.as_dicts = [{"Col": "Val"}]

        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_tables.return_value = [mock_table]
        mock_processor_class.return_value = mock_processor

        output_file = str(tmp_path / "tables.json")
        result = runner.invoke(app, ["pdf-extract-tables", "test.pdf", "--output", output_file])

        assert result.exit_code == 0
        assert Path(output_file).exists()


class TestPDFExtractInvoiceCommand:
    """Tests for pdf-extract-invoice command."""

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_invoice_success(self, mock_processor_class: MagicMock) -> None:
        """Test successful invoice extraction."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_invoice_data.return_value = {
            "invoice_number": "INV-001",
            "date": "2024-01-01",
            "total": "100.00",
        }
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-invoice", "invoice.pdf"])

        assert result.exit_code == 0
        mock_processor.extract_invoice_data.assert_called_once_with("invoice.pdf")

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_invoice_with_line_items(self, mock_processor_class: MagicMock) -> None:
        """Test invoice extraction with line items."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_invoice_data.return_value = {
            "invoice_number": "INV-001",
            "line_items": [{"item": "Widget", "price": "10.00"}],
        }
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-invoice", "invoice.pdf"])

        assert result.exit_code == 0

    @patch("src.cli.PDFProcessor")
    def test_pdf_extract_invoice_error(self, mock_processor_class: MagicMock) -> None:
        """Test invoice extraction handles errors."""
        mock_processor = MagicMock()
        mock_processor.__enter__ = MagicMock(return_value=mock_processor)
        mock_processor.__exit__ = MagicMock(return_value=False)
        mock_processor.extract_invoice_data.side_effect = ValueError("Invalid PDF")
        mock_processor_class.return_value = mock_processor

        result = runner.invoke(app, ["pdf-extract-invoice", "bad.pdf"])

        assert result.exit_code == 1


class TestEmailSendCommand:
    """Tests for email-send command."""

    @patch("src.cli.EmailClient")
    def test_email_send_success(self, mock_client_class: MagicMock) -> None:
        """Test successful email send."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "email-send",
                "--to",
                "recipient@example.com",
                "--subject",
                "Test Subject",
                "--body",
                "Test body",
            ],
        )

        assert result.exit_code == 0
        mock_client.send_email.assert_called_once()

    @patch("src.cli.EmailClient")
    def test_email_send_with_cc(self, mock_client_class: MagicMock) -> None:
        """Test email send with CC recipients."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "email-send",
                "--to",
                "recipient@example.com",
                "--subject",
                "Test",
                "--body",
                "Body",
                "--cc",
                "cc@example.com",
            ],
        )

        assert result.exit_code == 0
        email_arg = mock_client.send_email.call_args[0][0]
        assert "cc@example.com" in email_arg.cc

    @patch("src.cli.EmailClient")
    def test_email_send_multiple_recipients(self, mock_client_class: MagicMock) -> None:
        """Test email send with multiple recipients."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "email-send",
                "--to",
                "a@example.com,b@example.com",
                "--subject",
                "Test",
                "--body",
                "Body",
            ],
        )

        assert result.exit_code == 0
        email_arg = mock_client.send_email.call_args[0][0]
        assert len(email_arg.to) == 2

    @patch("src.cli.EmailClient")
    def test_email_send_error(self, mock_client_class: MagicMock) -> None:
        """Test email send handles errors."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.send_email.side_effect = Exception("SMTP error")
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "email-send",
                "--to",
                "recipient@example.com",
                "--subject",
                "Test",
                "--body",
                "Body",
            ],
        )

        assert result.exit_code == 1


class TestEmailFetchCommand:
    """Tests for email-fetch command."""

    @patch("src.cli.EmailClient")
    def test_email_fetch_success(self, mock_client_class: MagicMock) -> None:
        """Test successful email fetch."""
        from datetime import datetime

        from src.integrations.email_handler import ReceivedEmail

        mock_email = ReceivedEmail(
            uid=1,
            subject="Test Subject",
            from_address="sender@example.com",
            to=["me@example.com"],
            date=datetime(2024, 1, 15),
            body="Test body",
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.fetch_emails.return_value = [mock_email]
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["email-fetch"])

        assert result.exit_code == 0
        mock_client.fetch_emails.assert_called_once()

    @patch("src.cli.EmailClient")
    def test_email_fetch_with_options(self, mock_client_class: MagicMock) -> None:
        """Test email fetch with folder and limit options."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.fetch_emails.return_value = []
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "email-fetch",
                "--folder",
                "Sent",
                "--limit",
                "5",
                "--unread-only",
            ],
        )

        assert result.exit_code == 0
        mock_client.fetch_emails.assert_called_once_with(
            folder="Sent",
            limit=5,
            unread_only=True,
        )

    @patch("src.cli.EmailClient")
    def test_email_fetch_error(self, mock_client_class: MagicMock) -> None:
        """Test email fetch handles errors."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.fetch_emails.side_effect = Exception("IMAP error")
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["email-fetch"])

        assert result.exit_code == 1
