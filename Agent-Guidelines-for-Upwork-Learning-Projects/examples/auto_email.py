"""Example: Email automation workflows."""

from datetime import datetime, timedelta

from src.integrations.email_handler import Email, EmailClient, EmailConfig


def send_daily_report(
    recipients: list[str],
    report_data: dict[str, any],
    spreadsheet_id: str,
) -> None:
    """Send a daily report email with data from Google Sheets.

    Args:
        recipients: List of email addresses
        report_data: Dictionary with report metrics
        spreadsheet_id: Spreadsheet containing report data
    """
    config = EmailConfig()
    client = EmailClient(config=config)

    subject = f"Daily Report - {datetime.now().strftime('%Y-%m-%d')}"

    body = f"""
    Daily Automation Report
    ======================

    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

    Metrics:
    --------
    Total Records: {report_data.get('total_records', 0)}
    Processed: {report_data.get('processed', 0)}
    Errors: {report_data.get('errors', 0)}
    Success Rate: {report_data.get('success_rate', 0):.1f}%

    Spreadsheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}

    Best regards,
    Upwork Learning Automation
    """

    email_msg = Email(
        to=recipients,
        subject=subject,
        body=body,
    )

    with client:
        client.send_email(email_msg)


def send_alert_email(
    recipients: list[str],
    alert_type: str,
    message: str,
    severity: str = "info",
) -> None:
    """Send an alert email.

    Args:
        recipients: List of email addresses
        alert_type: Type of alert (error, warning, info)
        message: Alert message
        severity: Severity level
    """
    config = EmailConfig()
    client = EmailClient(config=config)

    emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "i")

    subject = f"[{severity.upper()}] {alert_type} Alert"

    body = f"""
    {emoji} {alert_type} Alert
    {emoji} {'=' * 40}

    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    Message:
    {message}

    This is an automated alert from the Upwork Learning system.
    """

    email_msg = Email(
        to=recipients,
        subject=subject,
        body=body,
    )

    with client:
        client.send_email(email_msg)


def fetch_and_process_emails(
    folder: str = "INBOX",
    from_date: datetime | None = None,
    mark_read: bool = True,
) -> list[dict[str, any]]:
    """Fetch emails and extract data for processing.

    Args:
        folder: IMAP folder to search
        from_date: Only fetch emails after this date
        mark_read: Mark fetched emails as read

    Returns:
        List of processed email data
    """
    config = EmailConfig()
    client = EmailClient(config=config)

    if from_date is None:
        from_date = datetime.now() - timedelta(days=7)

    with client:
        emails = client.fetch_emails(
            folder=folder,
            limit=50,
            since_date=from_date,
        )

        results = []
        for email in emails:
            data = {
                "uid": email.uid,
                "from": email.from_address,
                "subject": email.subject,
                "date": email.date.isoformat(),
                "body_preview": email.body[:200] if email.body else "",
                "attachments_count": len(email.attachments),
            }
            results.append(data)

            if mark_read:
                client.mark_as_read(email.uid, folder=folder)

    return results


def auto_reply_with_template(
    original_uid: int,
    template: str,
    sender_name: str = "Support Team",
) -> None:
    """Send an auto-reply to an email.

    Args:
        original_uid: UID of the email to reply to
        template: Message template (supports {sender_name} placeholder)
        sender_name: Name to use in the reply
    """
    config = EmailConfig()
    client = EmailClient(config=config)

    with client:
        emails = client.fetch_emails(limit=1)

        if not emails:
            return

        original = emails[0]

        reply_body = f"""
        Dear {original.from_address.split('@')[0]},

        Thank you for reaching out to us.

        {template.format(sender_name=sender_name)}

        Best regards,
        {sender_name}
        Upwork Learning
        """

        reply_email = Email(
            to=[original.from_address],
            subject=f"Re: {original.subject}",
            body=reply_body,
        )

        client.send_email(reply_email)


if __name__ == "__main__":
    send_alert_email(
        recipients=["admin@example.com"],
        alert_type="Process Complete",
        message="PDF processing completed successfully. 50 files processed.",
        severity="info",
    )
