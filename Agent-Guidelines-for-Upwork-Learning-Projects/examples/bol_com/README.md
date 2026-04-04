# Bol.com API Integration Example

This example demonstrates how to use the Bol.com Seller API to fetch product data and sync it with Google Sheets.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure credentials:
```bash
cp config.py.example config.py
# Edit config.py with your Bol.com API credentials
```

3. Set up Google Sheets credentials:
```bash
cp config/credentials.json.example config/credentials.json
# Add your Google service account JSON
```

## Usage

### Fetch Products
```bash
python -m examples.bol_com fetch-products --category electronics
```

### Sync to Google Sheets
```bash
python -m examples.bol_com sync-sheets --spreadsheet-id YOUR_ID --category books
```

### Export to CSV
```bash
python -m examples.bol_com export-csv --category toys --output products.csv
```

## API Documentation

- [Bol.com Seller API Documentation](https://api.bol.com/retailer/public/api-docs/)
- Authentication: OAuth 2.0
- Base URL: `https://api.bol.com/retailer`

## Features

- Product search by category
- Inventory status updates
- Price information
- Offer management
- Sync with Google Sheets for reporting
