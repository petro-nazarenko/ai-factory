# PDF Processing

The PDF processing module extracts text, tables, and structured data from PDF documents.

## Basic Usage

```python
from src.integrations.pdf_processor import PDFProcessor

processor = PDFProcessor()
with processor:
    processor.open("document.pdf")
    
    # Extract all text
    text = processor.extract_all_text()
    
    # Extract from specific pages
    pages = processor.extract_text(page_numbers=[0, 2, 4])
```

## Extracting Tables

```python
with processor:
    # Extract tables
    tables = processor.extract_tables()
    
    # Convert to list of dicts
    for table in tables:
        rows = table.as_dicts
        print(rows)
    
    # Or get all as dicts directly
    all_data = processor.extract_tables_as_dicts()
```

## Search by Keyword

```python
with processor:
    # Find text with context
    matches = processor.extract_by_keyword("invoice", context_chars=100)
    
    for match in matches:
        print(f"Page {match['page']}: {match['context']}")
```

## Invoice Extraction

```python
with processor:
    invoice = processor.extract_invoice_data("invoice.pdf")
    print(invoice)
    # {
    #     "invoice_number": "INV-2024-001",
    #     "date": "01-15-2024",
    #     "total": "150.00",
    #     "vat": "25.00",
    #     "line_items": [...]
    # }
```

## CLI Usage

```bash
# Extract text
python -m src.cli pdf-extract-text document.pdf

# Extract text from specific pages
python -m src.cli pdf-extract-text document.pdf --pages "0,2,4"

# Extract tables
python -m src.cli pdf-extract-tables document.pdf --output tables.json

# Extract invoice data
python -m src.cli pdf-extract-invoice invoice.pdf
```
