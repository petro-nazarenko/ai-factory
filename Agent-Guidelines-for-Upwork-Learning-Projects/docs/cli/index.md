# CLI Reference

The `upwork-learn` CLI provides commands for all integrations.

## Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |
| `--version` | Show version |

## Sheets Commands

See [Sheets CLI Reference](sheets.md) for detailed documentation.

```bash
# Read data
upwork-learn sheets-read --spreadsheet-id ID --range "A1:C10"

# Write data  
upwork-learn sheets-write --spreadsheet-id ID --range "A1" --values '[["A","B"]]'

# List worksheets
upwork-learn sheets-list --spreadsheet-id ID
```

## PDF Commands

See [PDF CLI Reference](pdf.md) for detailed documentation.

```bash
# Extract text
upwork-learn pdf-extract-text document.pdf

# Extract tables
upwork-learn pdf-extract-tables document.pdf --output tables.json

# Extract invoice data
upwork-learn pdf-extract-invoice invoice.pdf
```

## Email Commands

See [Email CLI Reference](Claude/projects/ai-factory/Agent-Guidelines-for-Upwork-Learning-Projects/docs/cli/email.md) for detailed documentation.

```bash
# Send email
upwork-learn email-send --to "a@b.com" --subject "Hi" --body "Hello"

# Fetch emails
upwork-learn email-fetch --folder INBOX --limit 20
```
