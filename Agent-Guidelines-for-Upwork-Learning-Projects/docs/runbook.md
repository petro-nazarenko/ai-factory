# Deployment Runbook

This guide covers everything needed to take `upwork-learn` from a fresh checkout
to a running, verified service.

---

## 1. Google Service Account Setup

### 1.1 Create a service account

1. Open [Google Cloud Console](https://console.cloud.google.com/) → **IAM & Admin** → **Service Accounts**.
2. Click **Create Service Account**.
   - Name: `upwork-learn-sa` (or any descriptive name)
   - Role: none required at creation time
3. Click **Done**.

### 1.2 Enable APIs

In **APIs & Services → Library**, enable:

- **Google Sheets API**
- **Google Drive API**

### 1.3 Download the key file

1. Open the service account → **Keys** tab → **Add Key → Create new key → JSON**.
2. Save the downloaded file as `credentials.json`.

### 1.4 Share target spreadsheets

Open each Google Spreadsheet you want the service to access, click **Share**, and
add the service account email (e.g. `upwork-learn-sa@<project>.iam.gserviceaccount.com`)
with **Editor** (write) or **Viewer** (read-only) permission.

---

## 2. Placing credentials.json

### Option A — file on disk (local / VM / bare-metal)

Put `credentials.json` at the default location expected by the app:

```
~/.config/upwork-learn/credentials.json
```

```bash
mkdir -p ~/.config/upwork-learn
cp /path/to/downloaded/credentials.json ~/.config/upwork-learn/credentials.json
chmod 600 ~/.config/upwork-learn/credentials.json
```

You can override the path with the env var `GOOGLE_SHEETS_CREDENTIALS_PATH` or
the CLI flag `--credentials`.

### Option B — base64 env var (Docker / Kubernetes / CI)

Encode the file and store it as a secret:

```bash
# Encode
CREDS_B64=$(base64 -w 0 /path/to/credentials.json)

# Verify round-trip
echo "$CREDS_B64" | base64 -d | python3 -m json.tool > /dev/null && echo "OK"
```

Set `GOOGLE_SHEETS_CREDENTIALS_JSON=$CREDS_B64` in your container environment,
secret manager, or CI pipeline. When this variable is present the app uses it
and never reads from disk.

---

## 3. Environment Variables

Create a `.env` file in the project root (never commit it) or export the
variables in your shell / container environment.

```dotenv
# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDENTIALS_PATH=~/.config/upwork-learn/credentials.json
# or (takes precedence over the path):
# GOOGLE_SHEETS_CREDENTIALS_JSON=<base64-encoded JSON>

GOOGLE_SHEETS_SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

# ── Email (SMTP outbound) ─────────────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-account@gmail.com
SMTP_PASSWORD=your-app-password          # use an App Password, not your account password

# ── Email (IMAP inbound) ──────────────────────────────────────────────────────
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your-account@gmail.com
IMAP_PASSWORD=your-app-password

# ── Bol.com (optional) ────────────────────────────────────────────────────────
BOL_COM_CLIENT_ID=
BOL_COM_CLIENT_SECRET=

# ── Application ───────────────────────────────────────────────────────────────
LOG_LEVEL=INFO           # DEBUG | INFO | WARNING | ERROR
ENVIRONMENT=production   # development | staging | production
```

> **Gmail App Password**: go to your Google Account → Security →
> 2-Step Verification → App passwords. Generate one for "Mail" / "Other".
> The SMTP/IMAP password fields **must** use this App Password, not your
> regular account password.

---

## 4. Installation

```bash
# 1. Create a virtual environment
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install the package and all dependencies
uv pip install -e ".[dev]"

# 3. Verify the CLI is available
upwork-learn version
```

---

## 5. Health Check Verification

After setting the env vars, run the built-in health check:

```bash
upwork-learn health
```

Expected output when everything is reachable:

```
SMTP smtp.gmail.com:587 — OK
IMAP imap.gmail.com:993 — OK
Google credentials — OK (~/.config/upwork-learn/credentials.json)
```

If any check fails the command exits with code 1 and prints the error.

### Manual TCP check (no app required)

```bash
# SMTP
nc -zv smtp.gmail.com 587

# IMAP
nc -zv imap.gmail.com 993
```

### Verify Google Sheets read access

```bash
upwork-learn sheets-read \
  --spreadsheet-id 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms \
  --range "Sheet1!A1:C3"
```

A table of cell values should appear. A `AuthenticationError` means the service
account credentials are wrong or the sheet has not been shared with the service
account email.

---

## 6. Running in Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install uv && uv pip install -e "." --system

# Pass secrets via environment — never bake them into the image
ENV GOOGLE_SHEETS_CREDENTIALS_JSON=""
ENV SMTP_HOST=smtp.gmail.com
ENV SMTP_PORT=587
# ... other vars

ENTRYPOINT ["upwork-learn"]
CMD ["version"]
```

```bash
docker build -t upwork-learn .
docker run --env-file .env upwork-learn health
```

---

## 7. Running as a systemd Service

```ini
# /etc/systemd/system/upwork-learn.service
[Unit]
Description=upwork-learn automation service
After=network.target

[Service]
Type=simple
User=upwork
WorkingDirectory=/opt/upwork-learn
EnvironmentFile=/opt/upwork-learn/.env
ExecStart=/opt/upwork-learn/.venv/bin/upwork-learn email-fetch --limit 50
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now upwork-learn
sudo journalctl -u upwork-learn -f
```

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `AuthenticationError: Credentials file not found` | `credentials.json` missing or wrong path | Check `GOOGLE_SHEETS_CREDENTIALS_PATH` or set `GOOGLE_SHEETS_CREDENTIALS_JSON` |
| `AuthenticationError: SMTP authentication failed` | Wrong App Password or 2FA not enabled | Generate a new App Password in Google Account settings |
| `IntegrationConnectionError: IMAP connection failed` | Firewall blocking port 993 | Verify `nc -zv imap.gmail.com 993`; check cloud security groups |
| `SpreadsheetNotFound` | Spreadsheet not shared with service account | Share the sheet with the service account email |
| `RateLimitError` | Google Sheets API quota exceeded | The app will auto-sleep on 429; consider reducing request frequency |
| Logs show no output | `LOG_LEVEL` too high | Set `LOG_LEVEL=DEBUG` |
