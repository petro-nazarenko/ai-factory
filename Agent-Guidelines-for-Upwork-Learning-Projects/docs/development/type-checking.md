# Type Checking

We use `mypy` with strict mode for type checking.

## Running mypy

```bash
# Check all source code
mypy src/

# Check with strict mode (default)
mypy --strict src/

# Generate report
mypy src/ --html-report html-report
```

## Configuration

See `pyproject.toml` for mypy configuration:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
disallow_untyped_defs = true
```

## Type Annotations

All functions should have type annotations:

```python
# Good
def process_data(data: list[dict[str, Any]]) -> dict[str, int]:
    ...

# Bad
def process_data(data):
    ...
```

## Generic Types

Use appropriate generic types:

```python
from typing import Optional, Sequence

# Optional value
def get_value(key: str) -> Optional[str]:
    ...

# Sequence of items
def process_items(items: Sequence[int]) -> list[int]:
    ...

# TypeVar for generics
from typing import TypeVar

T = TypeVar("T")

def first(items: Sequence[T]) -> Optional[T]:
    if items:
        return items[0]
    return None
```

## Protocols

Use protocols for structural typing:

```python
from typing import Protocol

class DataProcessor(Protocol):
    def process(self, data: str) -> int:
        ...

def run_processor(processor: DataProcessor) -> int:
    return processor.process("data")
```

## Working with External Libraries

Install type stubs for better type checking:

```bash
# Type stubs for popular libraries
pip install types-requests types-PyYAML
```

## GitHub Actions

Type checking runs in CI:

```yaml
- name: Type check
  run: mypy src/
```
