"""Bol.com API Client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from src.utils.logger import get_logger
from src.utils.retry import with_retry

logger = get_logger(__name__)


@dataclass
class ProductOffer:
    """Represents a product offer from Bol.com."""

    offer_id: str
    product_id: str
    title: str
    price: float
    condition: str
    fulfillment_method: str
    stock_quantity: int
    ean: str | None
    isbn: str | None
    availability_code: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass
class Product:
    """Represents a product from Bol.com."""

    product_id: str
    title: str
    description: str | None
    ean: str | None
    isbn: str | None
    brand: str | None
    category_path: list[str]
    images: list[str]
    offers: list[ProductOffer]


class BolComClient:
    """Client for Bol.com Seller API.

    Provides methods for interacting with the Bol.com Seller API
    to manage products, offers, and inventory.
    """

    BASE_URL = "https://api.bol.com/retailer"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._http_client: httpx.Client | None = None

    def __enter__(self) -> BolComClient:
        """Context manager entry."""
        if not self._access_token:
            self._authenticate()
        self._http_client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/vnd.retailer.v10+json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._http_client:
            self._http_client.close()

    def _authenticate(self) -> None:
        """Authenticate with Bol.com API using OAuth 2.0."""
        token_url = "https://login.bol.com/token"
        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    token_url,
                    data=data,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                token_data = response.json()
                self._access_token = token_data["access_token"]
                logger.info("Successfully authenticated with Bol.com API")
        except httpx.HTTPStatusError as e:
            logger.error("Authentication failed", status_code=e.response.status_code)
            raise

    @with_retry(max_attempts=3)
    def get_product(self, product_id: str) -> Product | None:
        """Get product details by product ID.

        Args:
            product_id: Bol.com product ID

        Returns:
            Product object or None if not found
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use context manager.")

        response = self._http_client.get(f"/products/{product_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()

        data = response.json()
        return self._parse_product(data)

    @with_retry(max_attempts=3)
    def search_products(
        self,
        category_id: str | None = None,
        search_term: str | None = None,
        limit: int = 50,
    ) -> list[Product]:
        """Search for products.

        Args:
            category_id: Category ID to filter by
            search_term: Search term
            limit: Maximum number of results

        Returns:
            List of matching products
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use context manager.")

        params: dict[str, Any] = {"limit": limit}
        if category_id:
            params["category_id"] = category_id
        if search_term:
            params["q"] = search_term

        response = self._http_client.get("/products", params=params)
        response.raise_for_status()

        data = response.json()
        products = []
        for item in data.get("products", []):
            products.append(self._parse_product(item))

        return products

    @with_retry(max_attempts=3)
    def get_offers(
        self,
        product_id: str,
        page: int = 1,
    ) -> list[ProductOffer]:
        """Get offers for a product.

        Args:
            product_id: Product ID
            page: Page number

        Returns:
            List of offers
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use context manager.")

        response = self._http_client.get(
            f"/products/{product_id}/offers",
            params={"page": page},
        )
        response.raise_for_status()

        data = response.json()
        offers = []
        for item in data.get("offers", []):
            offers.append(self._parse_offer(item))

        return offers

    def get_all_offers(self, product_id: str) -> list[ProductOffer]:
        """Get all offers for a product (handles pagination).

        Args:
            product_id: Product ID

        Returns:
            All offers for the product
        """
        all_offers = []
        page = 1

        while True:
            offers = self.get_offers(product_id, page=page)
            if not offers:
                break
            all_offers.extend(offers)

            if len(offers) < 50:
                break

            page += 1
            time.sleep(0.5)

        return all_offers

    def get_inventory(self) -> list[dict[str, Any]]:
        """Get inventory information for all products.

        Returns:
            List of inventory items
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use context manager.")

        response = self._http_client.get("/inventory")
        response.raise_for_status()

        return response.json().get("inventory", [])

    def get_inventory_by_product(self, product_id: str) -> list[dict[str, Any]]:
        """Get inventory for a specific product.

        Args:
            product_id: Product ID

        Returns:
            Inventory entries for the product
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use context manager.")

        response = self._http_client.get(f"/inventory/{product_id}")
        response.raise_for_status()

        return response.json().get("inventory", [])

    def _parse_product(self, data: dict[str, Any]) -> Product:
        """Parse product data from API response."""
        return Product(
            product_id=data.get("productId", ""),
            title=data.get("title", ""),
            description=data.get("description"),
            ean=data.get("ean"),
            isbn=data.get("isbn"),
            brand=data.get("brand"),
            category_path=data.get("categoryPath", []),
            images=[img.get("url") for img in data.get("images", []) if img.get("url")],
            offers=[],
        )

    def _parse_offer(self, data: dict[str, Any]) -> ProductOffer:
        """Parse offer data from API response."""
        created = data.get("created")
        updated = data.get("updated")

        return ProductOffer(
            offer_id=data.get("offerId", ""),
            product_id=data.get("productId", ""),
            title=data.get("title", ""),
            price=float(data.get("price", 0)),
            condition=data.get("condition", ""),
            fulfillment_method=data.get("fulfillmentMethod", ""),
            stock_quantity=data.get("stockQuantity", 0),
            ean=data.get("ean"),
            isbn=data.get("isbn"),
            availability_code=data.get("availability", {}).get("code") if isinstance(data.get("availability"), dict) else None,
            created_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
            updated_at=datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else None,
        )

    def to_dict(self, product: Product) -> dict[str, Any]:
        """Convert product to dictionary for spreadsheet export."""
        return {
            "Product ID": product.product_id,
            "Title": product.title,
            "EAN": product.ean or "",
            "ISBN": product.isbn or "",
            "Brand": product.brand or "",
            "Category": " > ".join(product.category_path) if product.category_path else "",
            "Description": product.description or "",
            "Images Count": len(product.images),
        }

    def offer_to_dict(self, offer: ProductOffer) -> dict[str, Any]:
        """Convert offer to dictionary for spreadsheet export."""
        return {
            "Offer ID": offer.offer_id,
            "Product ID": offer.product_id,
            "Title": offer.title,
            "Price": f"€{offer.price:.2f}" if offer.price else "",
            "Condition": offer.condition,
            "Fulfillment": offer.fulfillment_method,
            "Stock": offer.stock_quantity,
            "EAN": offer.ean or "",
            "ISBN": offer.isbn or "",
            "Availability": offer.availability_code or "",
            "Created": offer.created_at.strftime("%Y-%m-%d %H:%M") if offer.created_at else "",
            "Updated": offer.updated_at.strftime("%Y-%m-%d %H:%M") if offer.updated_at else "",
        }
