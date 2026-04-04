# Upwork Learning

Automation and Integration Tools for Upwork Projects.

A comprehensive Python library for building automation workflows with Google Sheets, PDF processing, email automation, and API integrations.

## Features

- **Google Sheets Integration** - Read, write, and sync data with Google Sheets
- **PDF Processing** - Extract text, tables, and structured data from PDFs
- **Email Automation** - Send emails, fetch inbox, and auto-reply workflows
- **API Integrations** - Tools for integrating with APIs like Bol.com
- **CLI Tools** - Command-line interface for all operations
- **Best Practices** - Type hints, testing, linting, documentation, and security scanning

## Use Case Catalog

Quick reference for common automation tasks. Each use case includes CLI command and Python API.

| # | Use Case | Input | Output | CLI Command | Python API | ENV Required |
|---|----------|-------|--------|------------|------------|-------------|
| 1 | **Read Google Sheet** | `spreadsheet_id`, `range` | 2D list `[["A","B"],["C","D"]]` | `python -m src.cli sheets-read -s ID -r "A1:C10"` | `GoogleSheetsClient.read_range()` | `GOOGLE_SHEETS_CREDENTIALS_PATH` |
| 2 | **Write to Google Sheet** | `spreadsheet_id`, `range`, `values` | Updated cells | `python -m src.cli sheets-write -s ID -r A1 --values '[["X"]]'` | `GoogleSheetsClient.write_range()` | `GOOGLE_SHEETS_*` |
| 3 | **List worksheets** | `spreadsheet_id` | List `["Sheet1","Sheet2"]` | `python -m src.cli sheets-list -s ID` | `GoogleSheetsClient.get_worksheets()` | `GOOGLE_SHEETS_*` |
| 4 | **Extract PDF text** | PDF file path | String with all text | `python -m src.cli pdf-extract-text doc.pdf` | `PDFProcessor.extract_all_text()` | - |
| 5 | **Extract PDF tables** | PDF file path | List of dicts `[{col: val}]` | `python -m src.cli pdf-extract-tables doc.pdf -o tables.json` | `PDFProcessor.extract_tables_as_dicts()` | - |
| 6 | **Extract invoice data** | Invoice PDF path | Dict `{invoice_number, date, total, vat}` | `python -m src.cli pdf-extract-invoice invoice.pdf` | `PDFProcessor.extract_invoice_data()` | - |
| 7 | **Search in PDF** | PDF path, keyword | Matches with context | - | `PDFProcessor.extract_by_keyword("invoice")` | - |
| 8 | **Send email** | `to`, `subject`, `body` | Sent status | `python -m src.cli email-send -t "a@b.com" -s "Hi" -b "Hello"` | `EmailClient.send_email()` | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` |
| 9 | **Fetch emails** | `folder`, `limit` | List `[ReceivedEmail(...)]` | `python -m src.cli email-fetch -f INBOX -l 10` | `EmailClient.fetch_emails()` | `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD` |
| 10 | **Mark email read** | UID | Updated flags | - | `EmailClient.mark_as_read(uid)` | `IMAP_*` |
| 11 | **Delete email** | UID | Moved to trash | - | `EmailClient.delete_email(uid)` | `IMAP_*` |
| 12 | **PDF → Google Sheets** | PDF path, spreadsheet_id | Synced table rows | - | `examples/pdf_to_sheets.py` | `GOOGLE_SHEETS_*` |
| 13 | **Bol.com → Sheets** | category, spreadsheet_id | Product catalog in Sheet | `python -m examples.bol_com.cli sync-sheets -s ID -c electronics` | `sync_to_sheets()` | `BOL_CLIENT_ID`, `BOL_CLIENT_SECRET` |
| 14 | **Daily report email** | recipients, data dict | Sent email | - | `examples/auto_email.py::send_daily_report()` | `SMTP_*`, `GOOGLE_SHEETS_*` |
| 15 | **Alert email** | recipients, alert_type, message | Sent alert | - | `examples/auto_email.py::send_alert_email()` | `SMTP_*` |

### Environment Variables

```bash
# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=config/credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password

# API Keys
BOL_CLIENT_ID=your_client_id
BOL_CLIENT_SECRET=your_client_secret
```

## Installation

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e .

# Using pip
pip install -e .
```

## Quick Start

### Python API

```python
from src.integrations.google_sheets import GoogleSheetsClient

# Read from Google Sheets
with GoogleSheetsClient(spreadsheet_id="YOUR_ID") as client:
    data = client.read_range("Sheet1!A1:C10")
    print(data)
```

```python
from src.integrations.pdf_processor import PDFProcessor

# Extract data from PDF
processor = PDFProcessor()
with processor:
    processor.open("invoice.pdf")
    text = processor.extract_all_text()
    tables = processor.extract_tables()
```

### CLI

```bash
# Read from Google Sheets
python -m src.cli sheets-read --spreadsheet-id ID --range "A1:C10"

# Extract text from PDF
python -m src.cli pdf-extract-text document.pdf

# Send email
python -m src.cli email-send --to "a@b.com" --subject "Hi" --body "Hello"
```

## Development

### Using Nox (Recommended)

```bash
# Install nox
uv pip install nox

# Run all quality checks
nox -s all

# Run specific session
nox -s lint          # Lint code
nox -s test          # Run tests with coverage
nox -s test-fast     # Run tests (faster)
nox -s typecheck     # Type check with mypy
nox -s format        # Format code
nox -s docs          # Build documentation
nox -s docs-serve    # Serve docs locally
nox -s security      # Secret scanning
nox -s spell         # Spell check

# Run specific test
nox -s test -- tests/integrations/test_google_sheets.py

# Install pre-commit hooks
nox -s install-hooks

# Clean build artifacts
nox -s clean
```

### Manual Commands

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Lint code
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Type check
mypy src/

# Build docs
mkdocs build --strict

# Secret scanning
gitleaks detect --source . -v

# Spell check
codespell src/ tests/ docs/
```

## Project Structure

```
upwork-learning/
├── src/
│   ├── integrations/     # Integration modules (Sheets, PDF, Email)
│   ├── utils/           # Utilities (logger, config, retry)
│   └── cli.py           # CLI entry point
├── tests/               # Test suite
├── examples/            # Example usage
│   ├── bol_com/         # Bol.com API integration
│   ├── pdf_to_sheets.py # PDF to Sheets workflow
│   └── auto_email.py    # Email automation examples
├── docs/                # MkDocs documentation
├── .github/
│   └── workflows/       # CI/CD pipelines
├── noxfile.py           # Development tasks
├── pyproject.toml       # Project configuration
└── .gitleaks.toml       # Secret scanning rules
```

## Documentation

Full documentation is available at:
- [GitHub Pages](https://petro-nazarenko.github.io/Agent-Guidelines-for-Upwork-Learning-Projects/)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Petr Nazarenko
