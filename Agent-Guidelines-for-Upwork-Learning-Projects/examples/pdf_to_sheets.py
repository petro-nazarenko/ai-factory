"""Example: PDF to Google Sheets workflow."""

from pathlib import Path

from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig
from src.integrations.pdf_processor import PDFProcessor


def extract_invoice_and_sync(
    pdf_path: str | Path,
    spreadsheet_id: str,
    sheet_name: str = "Invoices",
) -> dict[str, any]:
    """Extract invoice data from PDF and sync to Google Sheets.

    Args:
        pdf_path: Path to PDF invoice
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Target worksheet name

    Returns:
        Extracted invoice data
    """
    processor = PDFProcessor()
    sheets_config = GoogleSheetsConfig(
        credentials_path="config/credentials.json",
        spreadsheet_id=spreadsheet_id,
    )
    sheets_client = GoogleSheetsClient(config=sheets_config)

    with processor:
        invoice_data = processor.extract_invoice_data(pdf_path)

    values = [[
        invoice_data.get("invoice_number", ""),
        invoice_data.get("date", ""),
        invoice_data.get("total", ""),
        invoice_data.get("vat", ""),
    ]]

    with sheets_client:
        try:
            sheets_client.create_worksheet(title=sheet_name, rows=100, cols=4)
        except Exception:
            pass

        sheets_client.append_row(values[0], sheet_name=sheet_name)

    return invoice_data


def extract_tables_and_sync(
    pdf_path: str | Path,
    spreadsheet_id: str,
    sheet_name: str = "TableData",
) -> int:
    """Extract tables from PDF and sync to Google Sheets.

    Args:
        pdf_path: Path to PDF
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Target worksheet name

    Returns:
        Number of rows synced
    """
    processor = PDFProcessor()
    sheets_config = GoogleSheetsConfig(
        credentials_path="config/credentials.json",
        spreadsheet_id=spreadsheet_id,
    )
    sheets_client = GoogleSheetsClient(config=sheets_config)

    with processor:
        tables = processor.extract_tables(path=pdf_path)

    if not tables:
        return 0

    all_dicts = []
    for table in tables:
        all_dicts.extend(table.as_dicts)

    if not all_dicts:
        return 0

    headers = list(all_dicts[0].keys())
    values = [headers]
    for row in all_dicts:
        values.append(list(row.values()))

    with sheets_client:
        try:
            sheets_client.create_worksheet(title=sheet_name, rows=len(values) + 10, cols=len(headers))
        except Exception:
            pass

        sheets_client.write_range(
            range_name=f"{sheet_name}!A1",
            values=values,
            spreadsheet_id=spreadsheet_id,
        )

    return len(values) - 1


if __name__ == "__main__":
    invoice_path = "data/invoice.pdf"
    spreadsheet_id = "your_spreadsheet_id"

    invoice_data = extract_invoice_and_sync(invoice_path, spreadsheet_id)
    print(f"Extracted invoice: {invoice_data}")
