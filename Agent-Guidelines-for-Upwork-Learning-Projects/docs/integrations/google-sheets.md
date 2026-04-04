# Google Sheets Integration

The Google Sheets integration provides a Pythonic interface to read, write, and manipulate data in Google Sheets.

## Installation

Ensure you have Google Sheets API enabled and a service account credentials file.

## Configuration

```python
from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig

config = GoogleSheetsConfig(
    credentials_path="config/credentials.json",
    spreadsheet_id="your_spreadsheet_id",
)
```

## Reading Data

```python
with GoogleSheetsClient(config=config) as client:
    # Read a range
    data = client.read_range("Sheet1!A1:C10")
    
    # Get worksheet names
    worksheets = client.get_worksheets()
```

## Writing Data

```python
with GoogleSheetsClient(config=config) as client:
    # Write a range
    client.write_range("Sheet1!A1", [["A", "B"], ["C", "D"]])
    
    # Append a row
    client.append_row(["New", "Row", "Data"])
    
    # Update a single cell
    client.update_cell(row=1, col=1, value="New Value")
```

## Batch Operations

```python
with GoogleSheetsClient(config=config) as client:
    # Batch write multiple ranges
    client.batch_write([
        {"range": "Sheet1!A1", "values": [["A1"]]},
        {"range": "Sheet1!B1", "values": [["B1"]]},
    ])
```

## CLI Usage

```bash
# List worksheets
python -m src.cli sheets-list --spreadsheet-id YOUR_ID

# Read data
python -m src.cli sheets-read --spreadsheet-id YOUR_ID --range "Sheet1!A1:C10"

# Write data
python -m src.cli sheets-write --spreadsheet-id YOUR_ID --range "A1" --values '[["A","B"]]'
```
