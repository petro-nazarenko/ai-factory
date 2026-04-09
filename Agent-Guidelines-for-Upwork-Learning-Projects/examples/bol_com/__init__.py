"""Example: Bol.com API Integration."""

from examples.bol_com.client import BolComClient
from examples.bol_com.sync import sync_to_sheets as sync_to_sheets

if __name__ == "__main__":
    client_id = "your_client_id"
    client_secret = "your_client_secret"

    with BolComClient(client_id, client_secret) as client:
        products = client.search_products(category_id="electronics", limit=20)
        print(f"Found {len(products)} products")

        for product in products[:5]:
            print(f"  - {product.title} ({product.product_id})")
