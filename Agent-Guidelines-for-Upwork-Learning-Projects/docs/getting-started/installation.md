# Installation

## Requirements

- Python 3.11 or higher
- pip or uv package manager

## Using uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
uv venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install package
uv pip install -e .
```

## Using pip

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install package
pip install -e .
```

## Install Development Dependencies

```bash
# Using uv
uv pip install -e ".[dev]"

# Using pip
pip install -e ".[dev]"
```

## Verify Installation

```bash
python -m src.cli version
```

Should output: `upwork-learn v0.1.0`
