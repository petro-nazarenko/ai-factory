# CLAUDE.md — Project Context for Claude Code

## Project: Upwork Learning

**Python automation toolkit** for freelance/Upwork projects.
Integrations: Google Sheets, PDF processing, Email (SMTP/IMAP), Bol.com API.
Version: 0.1.0 · Python 3.11+ · entry point: `upwork-learn` CLI

---

## Architecture

```
src/
├── cli.py                        # Typer CLI — all user-facing commands
├── integrations/
│   ├── base.py                   # BaseIntegration, IntegrationConfig, exceptions
│   ├── google_sheets.py          # gspread wrapper (read/write/append/batch)
│   ├── email_handler.py          # smtplib + imapclient (send/fetch/mark/delete)
│   └── pdf_processor.py          # pdfplumber (text/tables/invoice extraction)
└── utils/
    ├── config.py                 # Pydantic Settings — loads from .env
    ├── logger.py                 # structlog structured logging (JSON)
    └── retry.py                  # with_retry() and with_timeout() decorators

tests/
├── test_cli.py                   # CLI command tests (typer CliRunner)
├── integrations/
│   ├── test_email_handler.py
│   ├── test_google_sheets.py
│   └── test_pdf_processor.py
└── utils/
    └── test_retry.py

examples/
└── bol_com/                      # Bol.com API client example (httpx, OAuth2)
```

---

## Key Design Decisions

- **All integrations** extend `BaseIntegration` (abc) from `src/integrations/base.py`.
  Pattern: `connect()` / `disconnect()` / context manager `__enter__`/`__exit__`.
- **Config** is a `@dataclass` extending `IntegrationConfig` per integration.
  Global app config via `Pydantic Settings` in `src/utils/config.py` (reads `.env`).
- **Retries**: `@with_retry(max_attempts=3)` decorator uses `tenacity` with exponential backoff.
- **Timeout**: `@with_timeout(seconds)` uses `concurrent.futures.ThreadPoolExecutor` — thread-safe, cross-platform (not `signal.SIGALRM`).
- **Logging**: `structlog` JSON logger. Get via `get_logger(__name__)`. Returns `structlog.stdlib.BoundLogger`.
- **Exception hierarchy**: `IntegrationError` → `RateLimitError`, `AuthenticationError`, `IntegrationConnectionError`.
  > `IntegrationConnectionError` (NOT `ConnectionError` — avoids shadowing the Python builtin).
- **Credentials**: `GoogleSheetsConfig.credentials_path` defaults to `~/.config/upwork-learn/credentials.json`. Can be overridden via `GOOGLE_SHEETS_CREDENTIALS_PATH` env var or CLI `--credentials`.

---

## Development Commands

```bash
# Tests
pytest -q                                    # fast run
pytest --cov=src --cov-report=term-missing   # with coverage

# Nox sessions
nox -s lint        # ruff check (must pass: 0 errors)
nox -s typecheck   # mypy strict (must pass: 0 errors)
nox -s test        # pytest + coverage in isolated venv
nox -s format_code # ruff format
nox -s all_checks  # lint + typecheck + test + spell

# CLI (after pip install -e .)
upwork-learn version
upwork-learn sheets-read --spreadsheet-id <ID> --range "Sheet1!A1:C10"
upwork-learn pdf-extract-text path/to/file.pdf
upwork-learn email-fetch --limit 5 --unread-only
```

---

## Environment Variables (.env)

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `GOOGLE_SHEETS_CREDENTIALS_PATH` | Path to service account JSON |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Default spreadsheet ID |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | SMTP config |
| `IMAP_HOST` / `IMAP_PORT` / `IMAP_USER` / `IMAP_PASSWORD` | IMAP config |
| `BOL_COM_CLIENT_ID` / `BOL_COM_CLIENT_SECRET` | Bol.com OAuth2 |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR |
| `ENVIRONMENT` | development / staging / production |

---

## Audit Status (2026-03-25)

Technical audit was completed. All 15 issues resolved:

**Fixed:**
- `gspread.Credentials` → `google.oauth2.service_account.Credentials`
- `pdf.is_encrypted` (non-existent attr) → metadata dict lookup
- Missing `import email.utils` in email_handler
- `str` passed as `Path` in CLI commands
- Unreachable `except socket.gaierror` in `connect_imap()` (wrong order)
- SMTP leak on partial `connect()` failure (added rollback)
- `signal.SIGALRM` in `with_timeout()` → `ThreadPoolExecutor`
- `to_csv_rows()` return type `Iterator[str]` → `list[str]`
- `ConnectionError` renamed to `IntegrationConnectionError`
- `credentials_path` default changed to `~/.config/upwork-learn/`
- mypy strict: 45 errors → 0
- CLI coverage: 0% → 95%
- Total coverage: 57% → 75%

**Remaining (low priority):**
- `src/integrations/base.py` 57%: `retry_with_backoff`, `_handle_rate_limit`, `_validate_config` untested
- `src/integrations/google_sheets.py` 58%: `batch_write`, `create_worksheet`, `delete_worksheet` untested
- `src/integrations/email_handler.py` 67%: IMAP operations (`mark_as_read`, `delete_email`, `get_folders`) untested
- `asyncio_mode` warning: needs `pytest-asyncio` installed in the active env

---

## Active Branch

Development branch: `claude/audit-python-project-MJZaZ`
Push target: `origin/claude/audit-python-project-MJZaZ`
