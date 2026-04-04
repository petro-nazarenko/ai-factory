"""CLI for Bol.com example."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from examples.bol_com.client import BolComClient
from examples.bol_com.sync import sync_to_sheets

app = typer.Typer(name="bol-com", help="Bol.com API CLI")
console = Console()


def get_client() -> BolComClient:
    """Get authenticated Bol.com client."""
    from examples.bol_com.config import config

    return BolComClient(
        client_id=config.BOL_CLIENT_ID,
        client_secret=config.BOL_CLIENT_SECRET,
    )


@app.command()
def fetch_products(
    category: Annotated[str | None, typer.Option("--category", "-c", help="Category ID")] = None,
    search: Annotated[str | None, typer.Option("--search", "-s", help="Search term")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Fetch products from Bol.com."""
    try:
        with get_client() as client:
            products = client.search_products(
                category_id=category,
                search_term=search,
                limit=limit,
            )

        table = Table(title=f"Products ({len(products)} found)")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("EAN", style="green")
        table.add_column("Brand", style="yellow")

        for product in products:
            table.add_row(
                product.product_id,
                product.title[:50] + "..." if len(product.title) > 50 else product.title,
                product.ean or "-",
                product.brand or "-",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def get_product(product_id: str) -> None:
    """Get details for a specific product."""
    try:
        with get_client() as client:
            product = client.get_product(product_id)

        if not product:
            console.print(f"[yellow]Product {product_id} not found[/yellow]")
            return

        console.print(f"\n[bold]Product:[/bold] {product.title}")
        console.print(f"[bold]ID:[/bold] {product.product_id}")
        console.print(f"[bold]EAN:[/bold] {product.ean or '-'}")

        if product.offers:
            offers_table = Table(title="Offers")
            offers_table.add_column("Price", style="green")
            offers_table.add_column("Condition", style="cyan")
            offers_table.add_column("Stock", style="yellow")

            for offer in product.offers[:10]:
                offers_table.add_row(
                    f"€{offer.price:.2f}",
                    offer.condition,
                    str(offer.stock_quantity),
                )

            console.print(offers_table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def sync_sheets(
    spreadsheet_id: Annotated[str, typer.Option("--spreadsheet-id", help="Google Sheets ID")],
    category: Annotated[str | None, typer.Option("--category", "-c")] = None,
    search: Annotated[str | None, typer.Option("--search", "-s")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 100,
) -> None:
    """Sync products to Google Sheets."""
    try:
        with get_client() as client:
            console.print("Fetching products...")
            products = client.search_products(
                category_id=category,
                search_term=search,
                limit=limit,
            )

            console.print(f"Found {len(products)} products, syncing to Sheets...")

            count = sync_to_sheets(client, products, spreadsheet_id)

            console.print(f"[green]Successfully synced {count} products to Google Sheets[/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def export_csv(
    category: Annotated[str | None, typer.Option("--category", "-c")] = None,
    search: Annotated[str | None, typer.Option("--search", "-s")] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "products.csv",
    limit: Annotated[int, typer.Option("--limit", "-l")] = 100,
) -> None:
    """Export products to CSV."""
    import csv

    try:
        with get_client() as client:
            products = client.search_products(
                category_id=category,
                search_term=search,
                limit=limit,
            )

        rows = [client.to_dict(p) for p in products]
        if not rows:
            console.print("[yellow]No products found[/yellow]")
            return

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        console.print(f"[green]Exported {len(rows)} products to {output}[/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
