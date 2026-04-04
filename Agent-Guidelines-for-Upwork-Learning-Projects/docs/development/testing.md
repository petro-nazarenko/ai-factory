# Testing

We use `pytest` for testing with comprehensive coverage.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── integrations/
│   ├── __init__.py
│   ├── test_google_sheets.py
│   ├── test_pdf_processor.py
│   └── test_email_handler.py
└── utils/
    ├── __init__.py
    └── test_retry.py
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/integrations/test_google_sheets.py

# Run tests matching pattern
pytest -k "test_read"

# Run with verbose output
pytest -v

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Writing Tests

```python
import pytest
from unittest.mock import MagicMock, patch

from src.integrations.google_sheets import GoogleSheetsClient

class TestGoogleSheetsClient:
    """Tests for Google Sheets client."""
    
    @pytest.fixture
    def client(self) -> GoogleSheetsClient:
        """Create test client."""
        config = GoogleSheetsConfig(
            credentials_path=Path("tests/fixtures/credentials.json"),
            spreadsheet_id="test_id",
        )
        return GoogleSheetsClient(config=config)
    
    @patch("src.integrations.google_sheets.gspread")
    def test_read_range(self, mock_gspread: MagicMock, client: GoogleSheetsClient) -> None:
        """Test reading a range."""
        # Arrange
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.values_get.return_value = {"values": [["A", "B"]]}
        client._spreadsheet = mock_spreadsheet
        
        # Act
        result = client.read_range("A1:B1")
        
        # Assert
        assert result == [["A", "B"]]
        mock_spreadsheet.values_get.assert_called_once()
```

## Fixtures

See `tests/conftest.py` for shared fixtures.

## Mocking External Services

```python
@patch("src.integrations.google_sheets.gspread")
def test_with_mocked_api(mock_gspread: MagicMock) -> None:
    """Test with mocked API."""
    # Mock the gspread module
    mock_gspread.authorize.return_value = MagicMock()
```

## Integration Tests

Mark integration tests with `@pytest.mark.integration`:

```python
@pytest.mark.integration
def test_real_api_call() -> None:
    """Integration test that calls real API."""
    # Requires actual credentials
    pass
```
