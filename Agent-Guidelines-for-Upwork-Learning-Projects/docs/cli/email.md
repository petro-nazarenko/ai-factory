# Email CLI Commands

## email-send

Send an email.

```bash
upwork-learn email-send [OPTIONS]
```

### Options

| Flag | Description |
|------|-------------|
| `-t, --to` | Recipient email(s), comma-separated (required) |
| `-s, --subject` | Email subject (required) |
| `-b, --body` | Email body (required) |
| `--cc` | CC recipients, comma-separated |

### Example

```bash
upwork-learn email-send \
  --to "recipient@example.com" \
  --subject "Daily Report" \
  --body "Report attached"

# Multiple recipients
upwork-learn email-send \
  --to "a@example.com,b@example.com" \
  --cc "manager@example.com" \
  --subject "Update" \
  --body "Status update"
```

## email-fetch

Fetch emails from IMAP server.

```bash
upwork-learn email-fetch [OPTIONS]
```

### Options

| Flag | Description |
|------|-------------|
| `-f, --folder` | IMAP folder name (default: INBOX) |
| `-l, --limit` | Maximum emails to fetch (default: 10) |
| `--unread-only` | Only fetch unread emails |
| `--all` | Fetch all emails (default) |

### Example

```bash
# Fetch recent emails
upwork-learn email-fetch

# Fetch only unread
upwork-learn email-fetch --unread-only

# Fetch from Sent folder
upwork-learn email-fetch --folder Sent --limit 50
```
