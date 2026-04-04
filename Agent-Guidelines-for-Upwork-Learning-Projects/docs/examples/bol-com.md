# Bol.com API Example

This example demonstrates integrating with the Bol.com Seller API.

## Setup

1. Get Bol.com API credentials from your Seller Portal
2. Configure credentials in `examples/bol_com/config.py`

## Usage

```python
from examples.bol_com.client import BolComClient

client = BolComClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
)

with client:
    # Search products
    products = client.search_products(category_id="electronics", limit=20)
    
    for product in products:
        print(f"{product.title} - {product.product_id}")
```

## Sync to Google Sheets

```python
from examples.bol_com.sync import sync_to_sheets

with BolComClient(client_id, client_secret) as client:
    products = client.search_products(category_id="books")
    sync_to_sheets(client, products, spreadsheet_id="YOUR_ID")
```

## CLI Commands

```bash
# Fetch products
python -m examples.bol_com.cli fetch-products --category electronics

# Get product details
python -m examples.bol_com.cli get-product PRODUCT_ID

# Export to CSV
python -m examples.bol_com.cli export-csv --category toys --output products.csv

# Sync to Google Sheets
python -m examples.bol_com.cli sync-sheets --spreadsheet-id YOUR_ID --category books
```
