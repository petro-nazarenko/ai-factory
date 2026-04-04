# PDF CLI Commands

## pdf-extract-text

Extract text from a PDF document.

```bash
upwork-learn pdf-extract-text [OPTIONS] PATH
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PATH` | Path to PDF file (required) |

### Options

| Flag | Description |
|------|-------------|
| `-p, --pages` | Comma-separated page numbers (0-indexed) |
| `-o, --output` | Output file path |

### Example

```bash
# Extract all text
upwork-learn pdf-extract-text document.pdf

# Extract specific pages
upwork-learn pdf-extract-text document.pdf --pages "0,2,4"

# Save to file
upwork-learn pdf-extract-text document.pdf --output text.txt
```

## pdf-extract-tables

Extract tables from a PDF document.

```bash
upwork-learn pdf-extract-tables [OPTIONS] PATH
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PATH` | Path to PDF file (required) |

### Options

| Flag | Description |
|------|-------------|
| `-o, --output` | Output JSON file path |

### Example

```bash
upwork-learn pdf-extract-tables document.pdf --output tables.json
```

## pdf-extract-invoice

Extract structured invoice data from a PDF.

```bash
upwork-learn pdf-extract-invoice [OPTIONS] PATH
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PATH` | Path to PDF file (required) |

### Example

```bash
upwork-learn pdf-extract-invoice invoice.pdf
```
