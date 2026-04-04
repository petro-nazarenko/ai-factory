# Contributing

We welcome contributions! Please follow these guidelines.

## Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/petro-nazarenko/Agent-Guidelines-for-Upwork-Learning-Projects.git
cd Agent-Guidelines-for-Upwork-Learning-Projects

# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

## Code Style

We use `ruff` for linting and formatting:

```bash
# Check code
ruff check src/ tests/

# Format code
ruff format src/ tests/
```

## Type Checking

We use `mypy` with strict mode:

```bash
mypy src/
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/integrations/test_google_sheets.py

# Run specific test
pytest tests/integrations/test_google_sheets.py::TestGoogleSheetsClient::test_read_range
```

## Commit Messages

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## Code Review

- All PRs require at least one approval
- Address review comments
- Keep changes focused
