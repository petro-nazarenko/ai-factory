# Sheets CLI Commands

## sheets-read

Read data from a Google Sheet range.

```bash
upwork-learn sheets-read [OPTIONS]
```

### Options

| Flag | Description |
|------|-------------|
| `-s, --spreadsheet-id` | Spreadsheet ID (required) |
| `-r, --range` | Range in A1 notation (required) |
| `-c, --credentials` | Path to credentials JSON |

### Example

```bash
upwork-learn sheets-read \
  --spreadsheet-id "1ABC123..." \
  --range "Sheet1!A1:C10"
```

## sheets-write

Write data to a Google Sheet range.

```bash
upwork-learn sheets-write [OPTIONS]
```

### Options

| Flag | Description |
|------|-------------|
| `-s, --spreadsheet-id` | Spreadsheet ID (required) |
| `-r, --range` | Range in A1 notation (required) |
| `-v, --values` | JSON array of values (required) |
| `-c, --credentials` | Path to credentials JSON |

### Example

```bash
upwork-learn sheets-write \
  --spreadsheet-id "1ABC123..." \
  --range "Sheet1!A1" \
  --values '[["Name","Age"],["John",30],["Jane",25]]'
```

## sheets-list

List worksheets in a spreadsheet.

```bash
upwork-learn sheets-list [OPTIONS]
```

### Options

| Flag | Description |
|------|-------------|
| `-s, --spreadsheet-id` | Spreadsheet ID (required) |
| `-c, --credentials` | Path to credentials JSON |

### Example

```bash
upwork-learn sheets-list --spreadsheet-id "1ABC123..."
```
