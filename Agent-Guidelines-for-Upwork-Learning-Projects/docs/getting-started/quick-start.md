# Quick Start

## Basic Usage

### 1. Read from Google Sheets

```bash
python -m src.cli sheets-read \
  --spreadsheet-id YOUR_SPREADSHEET_ID \
  --range "Sheet1!A1:C10"
```

### 2. Write to Google Sheets

```bash
python -m src.cli sheets-write \
  --spreadsheet-id YOUR_SPREADSHEET_ID \
  --range "Sheet1!A1" \
  --values '[["Header 1", "Header 2"], ["Value 1", "Value 2"]]'
```

### 3. Extract Text from PDF

```bash
python -m src.cli pdf-extract-text path/to/document.pdf
```

### 4. Extract Tables from PDF

```bash
python -m src.cli pdf-extract-tables path/to/document.pdf --output tables.json
```

### 5. Send Email

```bash
python -m src.cli email-send \
  --to "recipient@example.com" \
  --subject "Test Email" \
  --body "Hello from Upwork Learning!"
```

## Python API

### Google Sheets

```python
from src.integrations.google_sheets import GoogleSheetsClient

with GoogleSheetsClient(spreadsheet_id="YOUR_ID") as client:
    # Read data
    data = client.read_range("Sheet1!A1:C10")
    
    # Write data
    client.write_range("Sheet1!A1", [["A", "B"], ["C", "D"]])
    
    # Append row
    client.append_row(["New", "Row", "Data"])
```

### PDF Processing

```python
from src.integrations.pdf_processor import PDFProcessor

processor = PDFProcessor()
with processor:
    processor.open("invoice.pdf")
    
    # Extract all text
    text = processor.extract_all_text()
    
    # Extract tables as dicts
    tables = processor.extract_tables_as_dicts()
    
    # Extract invoice data
    invoice = processor.extract_invoice_data("invoice.pdf")
```

### Email

```python
from src.integrations.email_handler import EmailClient, Email

client = EmailClient()
with client:
    # Send email
    client.send_email(Email(
        to=["recipient@example.com"],
        subject="Subject",
        body="Body",
    ))
    
    # Fetch emails
    emails = client.fetch_emails(limit=10)
```
