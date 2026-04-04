# Workflows

This page demonstrates common automation workflows combining multiple integrations.

## PDF to Google Sheets

Automatically extract data from PDFs and sync to Google Sheets.

```python
from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig
from src.integrations.pdf_processor import PDFProcessor

def process_invoices(pdf_directory: str, spreadsheet_id: str):
    """Process all PDF invoices and sync to Sheets."""
    import os
    
    sheets_config = GoogleSheetsConfig(spreadsheet_id=spreadsheet_id)
    sheets_client = GoogleSheetsClient(config=sheets_config)
    processor = PDFProcessor()
    
    with sheets_client:
        # Create or clear invoice sheet
        try:
            sheets_client.create_worksheet("Invoices", rows=1000, cols=6)
        except Exception:
            pass
        
        for filename in os.listdir(pdf_directory):
            if filename.endswith(".pdf"):
                pdf_path = os.path.join(pdf_directory, filename)
                
                with processor:
                    invoice = processor.extract_invoice_data(pdf_path)
                
                row = [
                    filename,
                    invoice.get("invoice_number", ""),
                    invoice.get("date", ""),
                    invoice.get("total", ""),
                    invoice.get("vat", ""),
                ]
                
                sheets_client.append_row(row, sheet_name="Invoices")
                print(f"Processed: {filename}")
```

## Email to Google Sheets

Parse incoming emails and log to Sheets.

```python
from datetime import datetime, timedelta
from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig
from src.integrations.email_handler import EmailClient, EmailConfig

def sync_emails_to_sheet(spreadsheet_id: str, sheet_name: str = "Emails"):
    """Sync recent emails to Google Sheets."""
    sheets_config = GoogleSheetsConfig(spreadsheet_id=spreadsheet_id)
    sheets_client = GoogleSheetsClient(config=sheets_config)
    email_config = EmailConfig()
    email_client = EmailClient(config=email_config)
    
    headers = ["UID", "From", "Subject", "Date", "Body Preview"]
    
    with sheets_client, email_client:
        emails = email_client.fetch_emails(
            limit=50,
            since_date=datetime.now() - timedelta(days=7),
        )
        
        try:
            sheets_client.create_worksheet(sheet_name, rows=1000, cols=5)
        except Exception:
            pass
        
        rows = [headers]
        for email in emails:
            rows.append([
                str(email.uid),
                email.from_address,
                email.subject,
                email.date.strftime("%Y-%m-%d %H:%M"),
                email.body[:100] if email.body else "",
            ])
        
        sheets_client.write_range(f"{sheet_name}!A1", rows)
        print(f"Synced {len(emails)} emails")
```

## Scheduled Reports

Send daily reports with data from Google Sheets.

```python
from datetime import datetime
from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig
from src.integrations.email_handler import EmailClient, EmailConfig, Email

def send_daily_report(
    spreadsheet_id: str,
    report_sheet: str,
    recipients: list[str],
):
    """Send daily summary report."""
    sheets_config = GoogleSheetsConfig(spreadsheet_id=spreadsheet_id)
    sheets_client = GoogleSheetsClient(config=sheets_config)
    email_config = EmailConfig()
    email_client = EmailClient(config=email_config)
    
    with sheets_client:
        data = sheets_client.read_range(f"{report_sheet}!A1:Z100")
    
    total_rows = len(data) - 1  # Exclude header
    
    body = f"""
    Daily Report - {datetime.now().strftime('%Y-%m-%d')}
    
    Total Records: {total_rows}
    Data Sheet: {report_sheet}
    
    Spreadsheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}
    """
    
    email_msg = Email(
        to=recipients,
        subject=f"Daily Report - {datetime.now().strftime('%Y-%m-%d')}",
        body=body,
    )
    
    with email_client:
        email_client.send_email(email_msg)
```
