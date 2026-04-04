"""Tests for email handler."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from src.integrations.email_handler import (
    Email,
    EmailClient,
    EmailConfig,
    ReceivedEmail,
)

# Never hard-code credentials — read from env so gitleaks stays quiet.
_TEST_SECRET = SecretStr(os.environ.get("TEST_EMAIL_PASSWORD", "ci-placeholder"))


class TestEmailConfig:
    """Tests for email configuration."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = EmailConfig()
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.imap_host == "imap.gmail.com"
        assert config.imap_port == 993

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = EmailConfig(
            smtp_host="smtp.custom.com",
            smtp_port=465,
            smtp_user="test@test.com",
            smtp_password=_TEST_SECRET,
        )
        assert config.smtp_host == "smtp.custom.com"
        assert config.smtp_port == 465
        assert config.smtp_user == "test@test.com"


class TestEmail:
    """Tests for email dataclass."""

    def test_email_creation(self) -> None:
        """Test creating an email."""
        email_msg = Email(
            to=["recipient@example.com"],
            subject="Test Subject",
            body="Test body",
        )
        assert email_msg.to == ["recipient@example.com"]
        assert email_msg.subject == "Test Subject"
        assert email_msg.body == "Test body"
        assert email_msg.cc == []
        assert email_msg.bcc == []
        assert email_msg.attachments == []
        assert email_msg.html is False


class TestReceivedEmail:
    """Tests for received email dataclass."""

    def test_received_email_creation(self) -> None:
        """Test creating a received email."""
        email = ReceivedEmail(
            uid=123,
            subject="Test",
            from_address="sender@example.com",
            to=["recipient@example.com"],
            date=datetime.now(),
            body="Body",
        )
        assert email.uid == 123
        assert email.from_address == "sender@example.com"
        assert email.attachments == []
        assert email.flags == []


class TestEmailClient:
    """Tests for email client."""

    @pytest.fixture
    def config(self) -> EmailConfig:
        """Create test configuration."""
        return EmailConfig(
            smtp_user="test@gmail.com",
            smtp_password=_TEST_SECRET,
            imap_user="test@gmail.com",
            imap_password=_TEST_SECRET,
        )

    @pytest.fixture
    def client(self, config: EmailConfig) -> EmailClient:
        """Create test client."""
        return EmailClient(config=config)

    def test_service_name(self, client: EmailClient) -> None:
        """Test service name property."""
        assert client.service_name == "email"

    def test_initial_state(self, client: EmailClient) -> None:
        """Test initial client state."""
        assert client._connected is False
        assert client._smtp is None
        assert client._imap is None

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_connect_smtp(self, mock_smtp_class: MagicMock, client: EmailClient) -> None:
        """Test connecting to SMTP."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        client.connect_smtp()

        assert client._smtp is mock_smtp
        mock_smtp.ehlo.assert_called()
        mock_smtp.starttls.assert_called()
        mock_smtp.login.assert_called()

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_connect_imap(self, mock_imap_class: MagicMock, client: EmailClient) -> None:
        """Test connecting to IMAP."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap

        client.connect_imap()

        assert client._imap is mock_imap
        mock_imap.start_tls.assert_called()
        mock_imap.login.assert_called()

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_disconnect_smtp(self, mock_smtp_class: MagicMock, client: EmailClient) -> None:
        """Test disconnecting SMTP."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        client._smtp = mock_smtp

        client.disconnect_smtp()

        mock_smtp.quit.assert_called()
        assert client._smtp is None

    def test_disconnect_imap(self, client: EmailClient) -> None:
        """Test disconnecting IMAP."""
        mock_imap = MagicMock()
        client._imap = mock_imap

        client.disconnect_imap()

        mock_imap.logout.assert_called()
        assert client._imap is None

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_send_email(self, mock_smtp_class: MagicMock, client: EmailClient) -> None:
        """Test sending an email."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        client._smtp = mock_smtp

        email_msg = Email(
            to=["recipient@example.com"],
            subject="Test",
            body="Test body",
        )
        result = client.send_email(email_msg)

        assert result.get("status") == "sent"
        mock_smtp.send_message.assert_called()

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_send_email_simple(self, mock_smtp_class: MagicMock, client: EmailClient) -> None:
        """Test sending a simple email."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        client._smtp = mock_smtp

        result = client.send_email_simple(
            to="recipient@example.com",
            subject="Test",
            body="Test body",
        )

        assert result.get("status") == "sent"

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_send_email_multiple_recipients(
        self, mock_smtp_class: MagicMock, client: EmailClient
    ) -> None:
        """Test sending to multiple recipients."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        client._smtp = mock_smtp

        email_msg = Email(
            to=["a@example.com", "b@example.com"],
            subject="Test",
            body="Test body",
            cc=["cc@example.com"],
        )
        client.send_email(email_msg)

        mock_smtp.send_message.assert_called()

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_fetch_emails(self, mock_imap_class: MagicMock, client: EmailClient) -> None:
        """Test fetching emails."""
        mock_imap = MagicMock()
        mock_imap.search.return_value = [1, 2, 3]
        mock_imap.fetch.return_value = {
            1: {b"BODY[]": b"From: sender@test.com\r\nSubject: Test\r\n\r\nBody"},
            2: {b"BODY[]": b"From: sender2@test.com\r\nSubject: Test2\r\n\r\nBody2"},
            3: {b"BODY[]": b"From: sender3@test.com\r\nSubject: Test3\r\n\r\nBody3"},
        }
        mock_imap_class.return_value = mock_imap
        client._imap = mock_imap

        emails = client.fetch_emails(limit=10)

        assert len(emails) == 3
        mock_imap.select_folder.assert_called_with("INBOX", readonly=True)

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_mark_as_read(self, mock_imap_class: MagicMock, client: EmailClient) -> None:
        """Test marking email as read."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        client._imap = mock_imap

        client.mark_as_read(123)

        mock_imap.add_flags.assert_called_with(123, ["\\Seen"])

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_delete_email(self, mock_imap_class: MagicMock, client: EmailClient) -> None:
        """Test deleting an email."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        client._imap = mock_imap

        client.delete_email(123)

        mock_imap.move.assert_called_with(123, client._config.trash_folder)

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_get_folders(self, mock_imap_class: MagicMock, client: EmailClient) -> None:
        """Test getting folder list."""
        mock_imap = MagicMock()
        mock_imap.list_folders.return_value = [
            (b"\\HasNoChildren", b"/", "INBOX"),
            (b"\\HasNoChildren", b"/", "Sent"),
        ]
        mock_imap_class.return_value = mock_imap
        client._imap = mock_imap

        folders = client.get_folders()

        assert "INBOX" in folders
        assert "Sent" in folders

    def test_context_manager(self, config: EmailConfig) -> None:
        """Test context manager usage."""
        with patch("src.integrations.email_handler.smtplib.SMTP"):
            with patch("src.integrations.email_handler.imapclient.IMAPClient"):
                client = EmailClient(config=config)
                with client:
                    assert client._connected is True

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_mark_as_unread(self, mock_imap_class: MagicMock, client: EmailClient) -> None:
        """Test marking email as unread."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        client._imap = mock_imap

        client.mark_as_unread(123)

        mock_imap.remove_flags.assert_called_with(123, ["\\Seen"])

    def test_fetch_emails_raises_when_imap_none_after_connect(self, client: EmailClient) -> None:
        """Test fetch_emails raises IntegrationConnectionError when imap remains None."""
        from src.integrations.base import IntegrationConnectionError

        with patch.object(client, "connect_imap"):
            # After patched connect_imap, _imap is still None
            with pytest.raises(IntegrationConnectionError):
                client.fetch_emails()

    def test_send_email_html(self, client: EmailClient) -> None:
        """Test sending an HTML email."""
        mock_smtp = MagicMock()
        client._smtp = mock_smtp

        email_msg = Email(
            to=["recipient@example.com"],
            subject="HTML Test",
            body="<h1>Hello</h1>",
            html=True,
        )
        result = client.send_email(email_msg)

        assert result.get("status") == "sent"

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_fetch_emails_with_since_date(
        self, mock_imap_class: MagicMock, client: EmailClient
    ) -> None:
        """Test fetch_emails with since_date filter."""
        from datetime import datetime

        mock_imap = MagicMock()
        mock_imap.search.return_value = []
        mock_imap_class.return_value = mock_imap
        client._imap = mock_imap

        emails = client.fetch_emails(since_date=datetime(2024, 1, 1))

        assert emails == []
        call_args = mock_imap.search.call_args[0][0]
        assert any("SINCE" in str(c) for c in call_args)


class TestIMapValidators:
    """Tests for the static IMAP safety helpers added in fix 2.4."""

    def test_validate_folder_name_valid(self) -> None:
        EmailClient._validate_folder_name("INBOX")
        EmailClient._validate_folder_name("[Gmail]/Sent Mail")

    def test_validate_folder_name_rejects_crlf(self) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            EmailClient._validate_folder_name("INBOX\r\nA1 LOGOUT")

    def test_validate_folder_name_rejects_newline(self) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            EmailClient._validate_folder_name("INBOX\nINJECT")

    def test_validate_folder_name_rejects_null(self) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            EmailClient._validate_folder_name("INBOX\x00")

    def test_safe_imap_date_valid(self) -> None:
        from datetime import datetime

        result = EmailClient._safe_imap_date(datetime(2026, 1, 15))
        assert result == "15-Jan-2026"

    def test_fetch_emails_rejects_unsafe_folder(self) -> None:
        client = EmailClient()
        mock_imap = MagicMock()
        client._imap = mock_imap

        with pytest.raises(ValueError, match="unsafe"):
            client.fetch_emails(folder="INBOX\r\nLOGOUT")


class TestEmailClientErrorPaths:
    """Tests for error handling in SMTP / IMAP operations."""

    @pytest.fixture
    def config(self) -> EmailConfig:
        return EmailConfig(
            smtp_user="test@gmail.com",
            smtp_password=_TEST_SECRET,
            imap_user="test@gmail.com",
            imap_password=_TEST_SECRET,
        )

    @pytest.fixture
    def client(self, config: EmailConfig) -> EmailClient:
        return EmailClient(config=config)

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_connect_smtp_auth_error_raises_authentication_error(
        self, mock_smtp_class: MagicMock, client: EmailClient
    ) -> None:
        import smtplib

        from src.integrations.base import AuthenticationError

        mock_smtp = MagicMock()
        mock_smtp.starttls.return_value = None
        mock_smtp.ehlo.return_value = None
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_class.return_value = mock_smtp

        with pytest.raises(AuthenticationError):
            client.connect_smtp()

    @patch("src.integrations.email_handler.smtplib.SMTP")
    def test_connect_smtp_generic_error_raises_connection_error(
        self, mock_smtp_class: MagicMock, client: EmailClient
    ) -> None:
        import smtplib

        from src.integrations.base import IntegrationConnectionError

        mock_smtp_class.side_effect = smtplib.SMTPException("connection refused")

        with pytest.raises(IntegrationConnectionError):
            client.connect_smtp()

    def test_disconnect_smtp_swallows_quit_exception(self, client: EmailClient) -> None:
        mock_smtp = MagicMock()
        mock_smtp.quit.side_effect = Exception("already disconnected")
        client._smtp = mock_smtp

        client.disconnect_smtp()  # must not raise
        assert client._smtp is None

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_connect_imap_login_error_raises_authentication_error(
        self, mock_imap_class: MagicMock, client: EmailClient
    ) -> None:
        import imapclient.exceptions

        from src.integrations.base import AuthenticationError

        mock_imap = MagicMock()
        mock_imap.login.side_effect = imapclient.exceptions.LoginError("Bad credentials")
        mock_imap_class.return_value = mock_imap

        with pytest.raises(AuthenticationError):
            client.connect_imap()

    @patch("src.integrations.email_handler.imapclient.IMAPClient")
    def test_connect_imap_gaierror_raises_connection_error(
        self, mock_imap_class: MagicMock, client: EmailClient
    ) -> None:
        import socket

        from src.integrations.base import IntegrationConnectionError

        mock_imap_class.side_effect = socket.gaierror("Name not resolved")

        with pytest.raises(IntegrationConnectionError):
            client.connect_imap()

    def test_disconnect_imap_swallows_logout_exception(self, client: EmailClient) -> None:
        mock_imap = MagicMock()
        mock_imap.logout.side_effect = Exception("already gone")
        client._imap = mock_imap

        client.disconnect_imap()  # must not raise
        assert client._imap is None
