# ReSight

ReSight is a vanilla HTML/CSS/JavaScript research-paper frontend backed by a
FastAPI API, SQLAlchemy, and PostgreSQL. The API searches arXiv and optionally
uses Gemini to summarize abstracts; the feed continues with labeled
abstract-based summaries when Gemini is unavailable.

## Requirements

- Python 3.10 or later
- PostgreSQL
- SMTP credentials for signup verification, password reset, and user-triggered
  digests
- A Gemini API key is optional; without it, the feed displays abstract-based
  fallback summaries

## Backend setup

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

Edit `backend/.env` with a PostgreSQL SQLAlchemy URL and a unique random
`JWT_SECRET_KEY` of at least 32 characters. Set the SMTP sender and password
for email features. Do not commit `.env` files or place credentials in source
control. The API reads these settings from the process environment or
`backend/.env`; process environment values take precedence.

Start PostgreSQL, then start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API docs are at
`http://127.0.0.1:8000/docs`.

## Frontend setup and deployment

In another terminal, serve the static frontend from the repository root:

```powershell
.\.venv\Scripts\python.exe -m http.server 5500 --directory frontend
```

Open `http://127.0.0.1:5500`. The default API URL is local for `localhost` and
`127.0.0.1`; a non-local frontend defaults to a same-origin API (normally
through a reverse proxy). For a separately hosted frontend, configure the
public API URL by setting `window.RESIGHT_API_BASE_URL` in the deployment's
runtime bootstrap before `config.js` loads. The API URL is public configuration,
not a secret.

Set `CORS_ALLOWED_ORIGINS` on the backend to a comma-separated list of exact
frontend origins, including the deployed origin (scheme and host, and port when
nonstandard). Do not use `*` with credentials.

Use a production ASGI server configuration behind HTTPS, inject secrets through
the hosting platform's secret manager, and configure database network access
and backups before deployment. The application does not deploy infrastructure.

## Digests and email

The automated digest scheduler is **disabled by default**. To opt in, set
`DIGEST_SCHEDULER_ENABLED=true` and choose `DIGEST_INTERVAL_MINUTES` of at least
1440 (one day). The scheduler allows only one digest job instance at a time and
uses a PostgreSQL advisory lock to prevent concurrent sends from multiple API
workers/instances.
`POST /digest/send` is a separate, authenticated manual operation and emails
all subscribed users; do not invoke it as part of tests.

Signup verification and password-reset verification codes expire after five
minutes. Email endpoints require working SMTP configuration.

## Tests

From the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

The focused tests use fake users and mocked Gemini/email clients; they do not
connect to PostgreSQL, call arXiv/Gemini, send email, or start a scheduler.
Python syntax can be checked with:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -c "from pathlib import Path; files=[p for p in Path('backend').rglob('*.py') if '__pycache__' not in p.parts]; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in files]; print(f'Python syntax OK for {len(files)} source files')"
```

## Known limitations and rotation notice

- Startup creates missing SQLAlchemy tables but does not migrate existing
  schemas. Use a reviewed migration process for future schema changes.
- The current OTP storage is part of the existing user schema; deploys should
  preserve that table and existing records.
- A credential-shaped PostgreSQL URL is present in Git history. Treat it as
  exposed and rotate the database credential immediately if it was ever valid.
  Removing it from the latest source does not revoke historical copies.
- A production frontend URL, database, SMTP account, Gemini key, hosting
  configuration, and deployment validation have not been supplied or tested.
