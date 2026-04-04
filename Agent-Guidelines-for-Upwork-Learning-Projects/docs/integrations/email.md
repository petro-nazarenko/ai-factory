# Email Integration

The email module provides SMTP and IMAP functionality for sending and receiving emails.

## Sending Emails

```python
from src.integrations.email_handler import EmailClient, Email

client = EmailClient()
with client:
    # Simple email
    client.send_email_simple(
        to="recipient@example.com",
        subject="Subject",
        body="Body text",
    )
    
    # With CC
    client.send_email_simple(
        to=["a@example.com", "b@example.com"],
        subject="Subject",
        body="Body",
        cc=["cc@example.com"],
    )
    
    # Rich email with attachments
    client.send_email(Email(
        to=["recipient@example.com"],
        subject="Subject",
        body="Body",
        attachments=[
            ("report.pdf", pdf_bytes, "application/pdf"),
        ],
    ))
```

## Fetching Emails

```python
from datetime import datetime, timedelta

client = EmailClient()
with client:
    # Fetch recent emails
    emails = client.fetch_emails(limit=20)
    
    # Only unread
    unread = client.fetch_emails(unread_only=True)
    
    # Since specific date
    last_week = datetime.now() - timedelta(days=7)
    recent = client.fetch_emails(since_date=last_week)
    
    for email in emails:
        print(f"{email.from_address}: {email.subject}")
```

## Managing Emails

```python
with client:
    # Mark as read
    client.mark_as_read(uid=123)
    
    # Mark as unread
    client.mark_as_unread(uid=123)
    
    # Move to trash
    client.delete_email(uid=123)
```

## CLI Usage

```bash
# Send email
python -m src.cli email-send \
  --to "recipient@example.com" \
  --subject "Hello" \
  --body "Message body"

# Fetch emails
python -m src.cli email-fetch --folder INBOX --limit 10

# Fetch only unread
python -m src.cli email-fetch --unread-only
```
