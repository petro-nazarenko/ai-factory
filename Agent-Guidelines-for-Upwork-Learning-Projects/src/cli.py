"""CLI entry point using Typer."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from src import __version__
from src.integrations.email_handler import Email, EmailClient, EmailConfig
from src.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig
from src.integrations.pdf_processor import PDFProcessor
from src.utils.logger import bind_request_id, get_logger

app = typer.Typer(
    name="upwork-learn",
    help="Automation and Integration Tools for Upwork Projects",
    add_completion=False,
)
console = Console()
logger = get_logger(__name__)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"[bold blue]upwork-learn[/bold blue] v{__version__}")


@app.command()
def sheets_read(
    spreadsheet_id: Annotated[str, typer.Option("--spreadsheet-id", "-s", help="Spreadsheet ID")],
    range_name: Annotated[str, typer.Option("--range", "-r", help="Range in A1 notation")],
    credentials_path: Annotated[str | None, typer.Option("--credentials", "-c")] = None,
) -> None:
    """Read data from Google Sheets."""
    try:
        config = GoogleSheetsConfig(spreadsheet_id=spreadsheet_id)
        if credentials_path:
            config.credentials_path = Path(credentials_path)
        client = GoogleSheetsClient(config=config)

        with client:
            data = client.read_range(range_name)

        table = Table(title=f"Data from {range_name}")
        table.add_column("Row", style="cyan")
        table.add_column("Data")

        for i, row in enumerate(data):
            table.add_row(str(i + 1), " | ".join(str(cell) for cell in row))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def sheets_write(
    spreadsheet_id: Annotated[str, typer.Option("--spreadsheet-id", "-s", help="Spreadsheet ID")],
    range_name: Annotated[str, typer.Option("--range", "-r", help="Range in A1 notation")],
    values: Annotated[str, typer.Option("--values", "-v", help="JSON array of values")],
    credentials_path: Annotated[str | None, typer.Option("--credentials", "-c")] = None,
) -> None:
    """Write data to Google Sheets."""
    import json

    try:
        config = GoogleSheetsConfig(spreadsheet_id=spreadsheet_id)
        if credentials_path:
            config.credentials_path = Path(credentials_path)
        client = GoogleSheetsClient(config=config)

        data = json.loads(values)

        with client:
            client.write_range(range_name, data)

        console.print(f"[green]Successfully wrote {len(data)} rows[/green]")

    except json.JSONDecodeError as e:
        console.print("[bold red]Error:[/bold red] Invalid JSON format for values")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def sheets_list(
    spreadsheet_id: Annotated[str, typer.Option("--spreadsheet-id", "-s", help="Spreadsheet ID")],
    credentials_path: Annotated[str | None, typer.Option("--credentials", "-c")] = None,
) -> None:
    """List worksheets in a spreadsheet."""
    try:
        config = GoogleSheetsConfig(spreadsheet_id=spreadsheet_id)
        if credentials_path:
            config.credentials_path = Path(credentials_path)
        client = GoogleSheetsClient(config=config)

        with client:
            worksheets = client.get_worksheets()

        table = Table(title="Worksheets")
        table.add_column("Name", style="cyan")

        for ws in worksheets:
            table.add_row(ws)

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def pdf_extract_text(
    path: Annotated[str, typer.Argument(help="Path to PDF file")],
    pages: Annotated[
        str | None, typer.Option("--pages", "-p", help="Page numbers (comma-separated)")
    ] = None,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file")] = None,
) -> None:
    """Extract text from PDF."""
    try:
        processor = PDFProcessor()

        page_numbers = None
        if pages:
            page_numbers = [int(p.strip()) for p in pages.split(",")]

        with processor:
            if page_numbers:
                data = processor.extract_text(path=path, page_numbers=page_numbers)
            else:
                data = processor.extract_text(path=path)

        text = "\n\n".join(f"--- Page {i + 1} ---\n{text}" for i, text in data.items())

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(text)
            console.print(f"[green]Text extracted to {output}[/green]")
        else:
            console.print(text)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def pdf_extract_tables(
    path: Annotated[str, typer.Argument(help="Path to PDF file")],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file")] = None,
) -> None:
    """Extract tables from PDF."""
    import json

    try:
        processor = PDFProcessor()

        with processor:
            tables = processor.extract_tables(path=path)
            dicts = []
            for table in tables:
                dicts.extend(table.as_dicts)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(dicts, f, indent=2, ensure_ascii=False)
            console.print(f"[green]Tables extracted to {output}[/green]")
        else:
            console.print_json(data=dicts)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def pdf_extract_invoice(
    path: Annotated[str, typer.Argument(help="Path to PDF file")],
) -> None:
    """Extract invoice data from PDF."""
    try:
        processor = PDFProcessor()

        with processor:
            data = processor.extract_invoice_data(path)

        table = Table(title="Extracted Invoice Data")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        for key, value in data.items():
            if key != "line_items":
                table.add_row(key, str(value))

        console.print(table)

        if data.get("line_items"):
            console.print("\n[bold]Line Items:[/bold]")
            console.print_json(data=data["line_items"])

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def email_send(
    to: Annotated[str, typer.Option("--to", "-t", help="Recipient email(s), comma-separated")],
    subject: Annotated[str, typer.Option("--subject", "-s", help="Email subject")],
    body: Annotated[str, typer.Option("--body", "-b", help="Email body")],
    cc: Annotated[str | None, typer.Option("--cc", help="CC recipients, comma-separated")] = None,
) -> None:
    """Send an email."""
    try:
        config = EmailConfig()
        client = EmailClient(config=config)

        recipients = [r.strip() for r in to.split(",")]
        cc_list = [r.strip() for r in cc.split(",")] if cc else []

        email_msg = Email(
            to=recipients,
            subject=subject,
            body=body,
            cc=cc_list,
        )

        with client:
            client.send_email(email_msg)

        console.print("[green]Email sent successfully![/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def email_fetch(
    folder: Annotated[str, typer.Option("--folder", "-f", help="IMAP folder")] = "INBOX",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max emails to fetch")] = 10,
    unread_only: Annotated[
        bool, typer.Option("--unread-only/--all", help="Only fetch unread")
    ] = False,
) -> None:
    """Fetch emails from IMAP server."""
    try:
        config = EmailConfig()
        client = EmailClient(config=config)

        with client:
            emails = client.fetch_emails(
                folder=folder,
                limit=limit,
                unread_only=unread_only,
            )

        table = Table(title=f"Emails from {folder}")
        table.add_column("UID", style="cyan", width=6)
        table.add_column("From", style="yellow", width=20)
        table.add_column("Subject", style="white")
        table.add_column("Date", style="green", width=12)

        for email in emails:
            table.add_row(
                str(email.uid),
                email.from_address[:18] + "..."
                if len(email.from_address) > 18
                else email.from_address,
                email.subject[:40] + "..." if len(email.subject) > 40 else email.subject,
                email.date.strftime("%Y-%m-%d"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def health() -> None:
    """Check connectivity to configured external services."""
    import socket

    from src.utils.config import load_config

    cfg = load_config()
    all_ok = True

    # SMTP check
    smtp_host = cfg.email.smtp_host
    smtp_port = cfg.email.smtp_port
    try:
        with socket.create_connection((smtp_host, smtp_port), timeout=5):
            console.print(f"[green]SMTP {smtp_host}:{smtp_port} — OK[/green]")
    except OSError as e:
        console.print(f"[red]SMTP {smtp_host}:{smtp_port} — FAIL ({e})[/red]")
        all_ok = False

    # IMAP check
    imap_host = cfg.email.imap_host
    imap_port = cfg.email.imap_port
    try:
        with socket.create_connection((imap_host, imap_port), timeout=5):
            console.print(f"[green]IMAP {imap_host}:{imap_port} — OK[/green]")
    except OSError as e:
        console.print(f"[red]IMAP {imap_host}:{imap_port} — FAIL ({e})[/red]")
        all_ok = False

    # Credentials file check
    creds = cfg.google_sheets.credentials_path
    import os as _os

    creds_json = _os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if creds_json:
        console.print("[green]Google credentials — OK (env var)[/green]")
    elif creds.exists():
        console.print(f"[green]Google credentials — OK ({creds})[/green]")
    else:
        console.print(f"[yellow]Google credentials — NOT FOUND ({creds})[/yellow]")

    if not all_ok:
        raise typer.Exit(1)


def main() -> None:
    """Main entry point."""
    import logging as _logging

    from src.utils.config import load_config
    from src.utils.logger import configure_logging

    cfg = load_config()
    configure_logging(getattr(_logging, cfg.app.log_level, _logging.INFO))
    bind_request_id()
    app()


if __name__ == "__main__":
    main()
