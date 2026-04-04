"""Email handling using smtplib and imapclient."""

from __future__ import annotations

import email
import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import email.utils
import re
import smtplib
import socket
from dataclasses import dataclass, field
from datetime import datetime
from email.message import Message
from typing import Any, Protocol

import imapclient
from imapclient import IMAPClient
from pydantic import SecretStr

from src.integrations.base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfig,
    IntegrationConnectionError,
)
from src.utils.logger import get_logger
from src.utils.retry import with_retry

logger = get_logger(__name__)

# IMAP date token is strictly DD-Mon-YYYY (e.g. 01-Jan-2026).
# Any deviation would indicate the datetime was manipulated or strftime behaved
# unexpectedly, so we reject it early rather than let it reach the server.
_IMAP_DATE_RE = re.compile(
    r"^\d{2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}$"
)
# Characters that must never appear in an IMAP mailbox name sent over the wire.
_FOLDER_UNSAFE_RE = re.compile(r"[\r\n\x00]")


class EmailTemplateProtocol(Protocol):
    """Protocol for email templates."""

    def render(self, **kwargs: Any) -> str:
        """Render template with provided variables."""
        ...


@dataclass
class EmailConfig(IntegrationConfig):
    """Configuration for email integration."""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None

    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str | None = None
    imap_password: SecretStr | None = None
    trash_folder: str = "[Gmail]/Trash"


@dataclass
class Email:
    """Represents an email message."""

    to: list[str]
    subject: str
    body: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[tuple[str, bytes, str]] = field(default_factory=list)
    html: bool = False


@dataclass
class ReceivedEmail:
    """Represents a received email."""

    uid: int
    subject: str
    from_address: str
    to: list[str]
    date: datetime
    body: str
    html_body: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


class EmailClient(BaseIntegration):
    """Client for sending and receiving emails.

    Supports SMTP for sending and IMAP for receiving emails.
    Includes support for HTML emails, attachments, and templating.
    """

    _config: EmailConfig

    def __init__(self, config: EmailConfig | None = None) -> None:
        super().__init__(config)
        self._config = config or EmailConfig()
        self._smtp: smtplib.SMTP | None = None
        self._imap: IMAPClient | None = None

    @property
    def service_name(self) -> str:
        return "email"

    def connect(self) -> None:
        """Establish connections to SMTP and IMAP servers."""
        self.connect_smtp()
        try:
            self.connect_imap()
        except Exception:
            self.disconnect_smtp()
            raise
        self._connected = True
        self._logger.info("Connected to email servers")

    def disconnect(self) -> None:
        """Close all connections."""
        self.disconnect_smtp()
        self.disconnect_imap()
        self._connected = False

    def connect_smtp(self) -> None:
        """Connect to SMTP server."""
        try:
            self._smtp = smtplib.SMTP(self._config.smtp_host, self._config.smtp_port)
            self._smtp.ehlo()
            self._smtp.starttls()
            self._smtp.ehlo()

            if self._config.smtp_user and self._config.smtp_password:
                self._smtp.login(
                    self._config.smtp_user,
                    self._config.smtp_password.get_secret_value(),
                )

            self._logger.info(
                "Connected to SMTP",
                host=self._config.smtp_host,
                port=self._config.smtp_port,
            )
        except smtplib.SMTPAuthenticationError as e:
            raise AuthenticationError(f"SMTP authentication failed: {e}") from e
        except smtplib.SMTPException as e:
            raise IntegrationConnectionError(f"SMTP connection failed: {e}") from e

    def disconnect_smtp(self) -> None:
        """Disconnect from SMTP server."""
        if self._smtp:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None

    def connect_imap(self) -> None:
        """Connect to IMAP server."""
        try:
            self._imap = imapclient.IMAPClient(self._config.imap_host, port=self._config.imap_port)
            self._imap.start_tls()

            if self._config.imap_user and self._config.imap_password:
                self._imap.login(
                    self._config.imap_user,
                    self._config.imap_password.get_secret_value(),
                )

            self._logger.info(
                "Connected to IMAP",
                host=self._config.imap_host,
                port=self._config.imap_port,
            )
        except imapclient.exceptions.LoginError as e:
            raise AuthenticationError(f"IMAP authentication failed: {e}") from e
        except socket.gaierror as e:
            raise IntegrationConnectionError(f"IMAP connection failed: {e}") from e
        except Exception as e:
            raise IntegrationConnectionError(f"IMAP connection failed: {e}") from e

    def disconnect_imap(self) -> None:
        """Disconnect from IMAP server."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    @with_retry(max_attempts=3)
    def send_email(self, email_msg: Email) -> dict[str, Any]:
        """Send an email.

        Args:
            email_msg: Email message to send

        Returns:
            SMTP response
        """
        if not self._smtp:
            self.connect_smtp()

        try:
            msg = self._build_message(email_msg)
            if not self._smtp:
                raise IntegrationConnectionError("SMTP connection is not established")

            _ = self._smtp.send_message(
                msg,
                to_addrs=email_msg.to,
                mail_options=[],
                rcpt_options=[],
            )
            self._logger.info(
                "Sent email",
                to=email_msg.to,
                subject=email_msg.subject,
            )
            return {"status": "sent"}
        except smtplib.SMTPException as e:
            self._logger.error("Failed to send email", error=str(e))
            raise

    def send_email_simple(
        self,
        to: list[str] | str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a simple text email.

        Args:
            to: Recipient(s)
            subject: Email subject
            body: Email body
            cc: CC recipients

        Returns:
            SMTP response
        """
        if isinstance(to, str):
            to = [to]

        email_msg = Email(
            to=to,
            subject=subject,
            body=body,
            cc=cc or [],
        )
        return self.send_email(email_msg)

    def _build_message(self, email_msg: Email) -> Message:
        """Build email message object."""
        msg = email.mime.multipart.MIMEMultipart("mixed")
        msg["Subject"] = email_msg.subject
        msg["From"] = self._config.smtp_user or ""
        msg["To"] = ", ".join(email_msg.to)

        if email_msg.cc:
            msg["Cc"] = ", ".join(email_msg.cc)

        if email_msg.html:
            msg.attach(email.mime.text.MIMEText(email_msg.body, "html"))
        else:
            msg.attach(email.mime.text.MIMEText(email_msg.body, "plain"))

        for filename, content, mime_type in email_msg.attachments:
            part = email.mime.base.MIMEBase(mime_type.split("/")[0], mime_type.split("/")[1])
            part.set_payload(content)
            email.encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

        return msg

    @staticmethod
    def _safe_imap_date(dt: datetime) -> str:
        """Return a safe IMAP date string for a SEARCH SINCE criterion.

        Raises:
            ValueError: if the formatted string doesn't match the strict
                ``DD-Mon-YYYY`` pattern expected by the IMAP protocol.
        """
        formatted = dt.strftime("%d-%b-%Y")
        if not _IMAP_DATE_RE.match(formatted):
            raise ValueError(f"Invalid IMAP date format produced: {formatted!r}")
        return formatted

    @staticmethod
    def _validate_folder_name(folder: str) -> None:
        """Reject folder names that contain CRLF or null bytes.

        imapclient quotes mailbox names, but an explicit check here stops a
        malformed folder string from reaching the socket at all.

        Raises:
            ValueError: if *folder* contains unsafe characters.
        """
        if _FOLDER_UNSAFE_RE.search(folder):
            raise ValueError(
                f"Folder name contains unsafe characters: {folder!r}"
            )

    def fetch_emails(
        self,
        folder: str = "INBOX",
        limit: int = 10,
        unread_only: bool = False,
        since_date: datetime | None = None,
    ) -> list[ReceivedEmail]:
        """Fetch emails from a folder.

        Args:
            folder: IMAP folder name
            limit: Maximum number of emails to fetch
            unread_only: Only fetch unread emails
            since_date: Only fetch emails after this date

        Returns:
            List of received emails
        """
        if not self._imap:
            self.connect_imap()
        if self._imap is None:
            raise IntegrationConnectionError("IMAP connection is not established")

        self._validate_folder_name(folder)

        try:
            self._imap.select_folder(folder, readonly=True)

            search_criteria = ["ALL"]
            if unread_only:
                search_criteria = ["UNSEEN"]
            if since_date:
                search_criteria.append(f"SINCE {self._safe_imap_date(since_date)}")

            message_ids = self._imap.search(search_criteria)

            if limit:
                message_ids = message_ids[-limit:]

            emails = []
            for uid in message_ids:
                try:
                    email_data = self._imap.fetch(uid, ["ENVELOPE", "BODY[]"])
                    msg_dict = email_data[uid]

                    if b"BODY[]" in msg_dict:
                        raw_email = msg_dict[b"BODY[]"]
                        msg = email.message_from_bytes(raw_email)
                        received_email = self._parse_email_message(uid, msg)
                        emails.append(received_email)
                except Exception as e:
                    self._logger.warning("Failed to fetch email", uid=uid, error=str(e))

            self._logger.info(
                "Fetched emails",
                folder=folder,
                count=len(emails),
            )
            return emails

        except imapclient.IMAPClient.Error as e:
            self._logger.error("Failed to fetch emails", error=str(e))
            raise

    def mark_as_read(self, uid: int, folder: str = "INBOX") -> None:
        """Mark an email as read.

        Args:
            uid: Email UID
            folder: Folder name
        """
        if not self._imap:
            self.connect_imap()
        if self._imap is None:
            raise IntegrationConnectionError("IMAP connection is not established")

        try:
            self._imap.select_folder(folder)
            self._imap.add_flags(uid, ["\\Seen"])
            self._logger.debug("Marked email as read", uid=uid)
        except Exception as e:
            self._logger.error("Failed to mark as read", uid=uid, error=str(e))
            raise

    def mark_as_unread(self, uid: int, folder: str = "INBOX") -> None:
        """Mark an email as unread.

        Args:
            uid: Email UID
            folder: Folder name
        """
        if not self._imap:
            self.connect_imap()
        if self._imap is None:
            raise IntegrationConnectionError("IMAP connection is not established")

        try:
            self._imap.select_folder(folder)
            self._imap.remove_flags(uid, ["\\Seen"])
            self._logger.debug("Marked email as unread", uid=uid)
        except Exception as e:
            self._logger.error("Failed to mark as unread", uid=uid, error=str(e))
            raise

    def delete_email(self, uid: int, folder: str = "INBOX") -> None:
        """Move email to trash.

        Args:
            uid: Email UID
            folder: Folder name
        """
        if not self._imap:
            self.connect_imap()
        if self._imap is None:
            raise IntegrationConnectionError("IMAP connection is not established")

        try:
            self._imap.select_folder(folder)
            self._imap.move(uid, self._config.trash_folder)
            self._logger.debug("Deleted email", uid=uid)
        except Exception as e:
            self._logger.error("Failed to delete email", uid=uid, error=str(e))
            raise

    def _parse_email_message(self, uid: int, msg: Message) -> ReceivedEmail:
        """Parse raw email message to ReceivedEmail."""
        subject = msg.get("Subject", "")
        from_address = msg.get("From", "")
        to_addresses = msg.get("To", "").split(", ")
        date_str = msg.get("Date", "")

        try:
            date = email.utils.parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            date = datetime.now()

        body = ""
        html_body = None
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get("Content-Disposition", "")

                if content_disposition and "attachment" in content_disposition:
                    filename = part.get_filename() or "unknown"
                    payload = part.get_payload(decode=True)
                    if payload:
                        attachments.append(
                            {
                                "filename": filename,
                                "content_type": content_type,
                                "size": len(payload),
                            }
                        )

                elif content_type == "text/plain" and not content_disposition:
                    raw = part.get_payload(decode=True)
                    body = (
                        raw.decode("utf-8", errors="replace")
                        if isinstance(raw, bytes)
                        else str(raw or "")
                    )

                elif content_type == "text/html" and not content_disposition:
                    raw_html = part.get_payload(decode=True)
                    html_body = (
                        raw_html.decode("utf-8", errors="replace")
                        if isinstance(raw_html, bytes)
                        else str(raw_html or "")
                    )
        else:
            raw = msg.get_payload(decode=True)
            body = (
                raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
            )

        return ReceivedEmail(
            uid=uid,
            subject=subject,
            from_address=from_address,
            to=to_addresses,
            date=date,
            body=body,
            html_body=html_body,
            attachments=attachments,
        )

    def get_folders(self) -> list[str]:
        """Get list of available IMAP folders.

        Returns:
            List of folder names
        """
        if not self._imap:
            self.connect_imap()
        if self._imap is None:
            raise IntegrationConnectionError("IMAP connection is not established")

        folders = self._imap.list_folders()
        return [f[2] for f in folders]
