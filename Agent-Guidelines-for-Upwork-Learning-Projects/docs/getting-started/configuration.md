# Configuration

## Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

### Google Sheets Configuration

```bash
GOOGLE_SHEETS_CREDENTIALS_PATH=config/credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

### Email Configuration

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password
```

### API Keys

```bash
BOL_COM_API_KEY=your_api_key
BOL_CLIENT_ID=your_client_id
BOL_CLIENT_SECRET=your_client_secret
```

## Google Service Account

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Sheets API
4. Create a service account
5. Download the JSON credentials
6. Place the file at `config/credentials.json`

## Gmail App Password

For Gmail, you need an App Password:

1. Enable 2-Factor Authentication on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a new app password for "Mail"
4. Use this password in your configuration
