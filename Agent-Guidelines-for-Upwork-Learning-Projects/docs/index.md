# Home

Welcome to **Upwork Learning** - a collection of automation and integration tools for Upwork projects.

## Features

- **Google Sheets Integration** - Read, write, and sync data with Google Sheets
- **PDF Processing** - Extract text, tables, and structured data from PDFs
- **Email Automation** - Send emails, fetch inbox, and auto-reply workflows
- **API Integrations** - Tools for integrating with APIs like Bol.com

## Quick Start

```bash
# Install dependencies
pip install -e .

# Configure credentials
cp .env.example .env
# Edit .env with your credentials

# Run CLI
python -m src.cli sheets-list --spreadsheet-id YOUR_ID
```

## Documentation

- [Installation Guide](Claude/projects/ai-factory/Agent-Guidelines-for-Upwork-Learning-Projects/docs/getting-started/installation.md)
- [Configuration](Claude/projects/ai-factory/Agent-Guidelines-for-Upwork-Learning-Projects/docs/getting-started/configuration.md)
- [Quick Start Tutorial](quick-start.md)

## Example Usage

### Google Sheets

```python
from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig

config = GoogleSheetsConfig(
    credentials_path="config/credentials.json",
    spreadsheet_id="your_spreadsheet_id",
)
client = GoogleSheetsClient(config=config)

with client:
    data = client.read_range("Sheet1!A1:C10")
    print(data)
```

### PDF Processing

```python
from src.integrations.pdf_processor import PDFProcessor

processor = PDFProcessor()
with processor:
    processor.open("invoice.pdf")
    text = processor.extract_all_text()
    tables = processor.extract_tables()
```

## Support

For issues and questions, please open an issue on [GitHub](https://github.com/petro-nazarenko/Agent-Guidelines-for-Upwork-Learning-Projects/issues).
