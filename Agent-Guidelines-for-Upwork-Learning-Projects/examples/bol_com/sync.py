"""Sync products to Google Sheets."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from examples.bol_com.client import BolComClient, Product


def sync_to_sheets(
    client: "BolComClient",
    products: list["Product"],
    spreadsheet_id: str,
    sheet_name: str = "Products",
) -> int:
    """Sync products to Google Sheets.

    Args:
        client: Authenticated Bol.com client
        products: List of products to sync
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Name of the worksheet

    Returns:
        Number of products synced
    """
    from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig

    if not products:
        return 0

    config = GoogleSheetsConfig(
        credentials_path="config/credentials.json",
        spreadsheet_id=spreadsheet_id,
    )
    sheets_client = GoogleSheetsClient(config=config)

    rows = [client.to_dict(p) for p in products]

    headers = list(rows[0].keys())
    data = [headers]
    for row in rows:
        data.append(list(row.values()))

    with sheets_client:
        try:
            sheets_client.create_worksheet(title=sheet_name, rows=len(data) + 10, cols=len(headers))
        except Exception:
            pass

        sheets_client.write_range(
            range_name=f"{sheet_name}!A1",
            values=data,
            spreadsheet_id=spreadsheet_id,
        )

    return len(products)


def sync_offers_to_sheets(
    client: "BolComClient",
    product_id: str,
    spreadsheet_id: str,
    sheet_name: str = "Offers",
) -> int:
    """Sync offers for a product to Google Sheets.

    Args:
        client: Authenticated Bol.com client
        product_id: Product ID
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Name of the worksheet

    Returns:
        Number of offers synced
    """
    from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig

    offers = client.get_all_offers(product_id)
    if not offers:
        return 0

    config = GoogleSheetsConfig(
        credentials_path="config/credentials.json",
        spreadsheet_id=spreadsheet_id,
    )
    sheets_client = GoogleSheetsClient(config=config)

    rows = [client.offer_to_dict(o) for o in offers]

    headers = list(rows[0].keys())
    data = [headers]
    for row in rows:
        data.append(list(row.values()))

    with sheets_client:
        try:
            sheets_client.create_worksheet(title=sheet_name, rows=len(data) + 10, cols=len(headers))
        except Exception:
            pass

        sheets_client.write_range(
            range_name=f"{sheet_name}!A1",
            values=data,
            spreadsheet_id=spreadsheet_id,
        )

    return len(offers)
