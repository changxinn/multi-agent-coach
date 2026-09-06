# Local Validation Without Docker Compose

This runbook validates the local request path without Docker Compose:

```text
Browser (http://localhost:5174)
  -> Main API (http://localhost:8000/api)
  -> private Nutrition Agent (http://localhost:8003)
  -> local PostgreSQL (localhost:5432)
```

Use four PowerShell terminals. The Nutrition Agent is an internal service: do not configure the browser to use port `8003`, and never put `NUTRITION_INTERNAL_SERVICE_TOKEN` in frontend `VITE_*` variables.

## Prerequisites

- `uv` is installed and can provision CPython 3.12. The standalone Nutrition Agent uses pinned dependencies with Windows wheels for CPython 3.12; do not use a root-project virtual environment created with Python 3.14.
- Node.js dependencies have been installed under `C:\dev\multi-agent-coach\frontend`.
- PostgreSQL is running locally and the database named by `DATABASE_URL` already exists.
- `C:\dev\multi-agent-coach\.env` contains the required API credentials and the correct local database password.

Confirm PostgreSQL is listening before beginning:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5432
```

## 1. Configure the main API environment

In `C:\dev\multi-agent-coach\.env`, set or confirm the following values. Replace `YOUR_PASSWORD` and the OpenAI key with real local-development values. Do not commit this file.

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/systemdb
DATABASE_SCHEMA=systemdb
JWT_SECRET_KEY=replace-with-a-local-secret-at-least-32-characters
OPENAI_API_KEY=your-key-if-required-by-your-chat-configuration

FRONTEND_URL=http://localhost:5174
ALLOWED_ORIGINS=http://localhost:5174,http://localhost:3000

USE_NUTRITION_AGENT_SERVICE=true
NUTRITION_AGENT_URL=http://localhost:8003
NUTRITION_AGENT_ROLLOUT_PERCENT=100
NUTRITION_INTERNAL_SERVICE_TOKEN=local-dev-nutrition-token
NUTRITION_LLM_ENABLED=false
```

`NUTRITION_AGENT_ROLLOUT_PERCENT=100` forces eligible nutrition chat traffic to the Nutrition Agent rather than leaving it in the local chat fallback path.

## 2. Apply and verify migrations

> **Warning:** Migrations modify the database configured by `DATABASE_URL`. Confirm that it is a local development database before running this command. Migrations do not create the PostgreSQL database itself.

**Terminal 1** — repository root:

```powershell
Set-Location C:\dev\multi-agent-coach
uv run python -m app.db.migrate
uv run python -m app.db.migrate --check
```

The first command applies pending versioned schema changes and records them in the migration ledger. The `--check` command is read-only and verifies compatibility.

## 3. Start the private Nutrition Agent

**Terminal 2** — Nutrition Agent directory:

```powershell
Set-Location C:\dev\multi-agent-coach\services\nutrition_agent

# Leave another active virtual environment before creating the service-local one.
if (Test-Path Env:VIRTUAL_ENV) { deactivate }

# One-time setup: create the Nutrition Agent environment with CPython 3.12.
uv python install 3.12
uv venv --python 3.12 .venv

# uv venv does not necessarily seed pip, so install with uv pip instead of
# python -m pip. Target the service-local interpreter explicitly.
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt

# Confirm portable IANA timezone data is installed before starting the service.
.\.venv\Scripts\python.exe -c "import tzdata; from zoneinfo import ZoneInfo; print(tzdata.__version__); print(ZoneInfo('Asia/Singapore').key)"
```

The final command must print `Asia/Singapore`. The setup commands are safe to rerun after changing `requirements.txt`.

Run the service using one of the following alternatives.

**Recommended: use the service-local interpreter directly** (this avoids ambiguity when another virtual environment is active):

```powershell
# Supply these explicitly because this process runs from the service directory.
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/systemdb'
$env:DATABASE_SCHEMA = 'systemdb'
$env:NUTRITION_INTERNAL_SERVICE_TOKEN = 'local-dev-nutrition-token'
$env:NUTRITION_LLM_ENABLED = 'false'

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8003
```

**Alternative: activate the service-local environment first**:

```powershell
.\.venv\Scripts\Activate.ps1

# Supply these explicitly because this process runs from the service directory.
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/systemdb'
$env:DATABASE_SCHEMA = 'systemdb'
$env:NUTRITION_INTERNAL_SERVICE_TOKEN = 'local-dev-nutrition-token'
$env:NUTRITION_LLM_ENABLED = 'false'

python -m uvicorn app.main:app --reload --port 8003
```

Starting it from this directory is required because both the repository root and this directory contain an `app` Python package. The activation alternative changes only the current PowerShell terminal; use `deactivate` when finished.

In a separate PowerShell prompt, wait for health checks to pass:

```powershell
Invoke-RestMethod http://localhost:8003/health/live
Invoke-RestMethod http://localhost:8003/health/ready
```

Expected readiness shape:

```json
{"status":"ready","checks":{"configuration":"ok","database":"ok","schema":"ok"}}
```

## 4. Start the main API

**Terminal 3** — repository root:

```powershell
Set-Location C:\dev\multi-agent-coach

# These override .env only in this terminal and make delegation unambiguous.
$env:USE_NUTRITION_AGENT_SERVICE = 'true'
$env:NUTRITION_AGENT_URL = 'http://localhost:8003'
$env:NUTRITION_AGENT_ROLLOUT_PERCENT = '100'
$env:NUTRITION_INTERNAL_SERVICE_TOKEN = 'local-dev-nutrition-token'

uv run python -m uvicorn app.main:app --reload --port 8000
```

Verify its health from another prompt:

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

Open the public API documentation at <http://localhost:8000/docs>.

## 5. Start the frontend

Create or update `C:\dev\multi-agent-coach\frontend\.env` with only browser-safe configuration:

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_FRONTEND_BASE_URL=http://localhost:5174
```

**Terminal 4** — frontend directory:

```powershell
Set-Location C:\dev\multi-agent-coach\frontend
npm run dev
```

Open <http://localhost:5174>, register a user, sign in, and send a nutrition-specific request, for example:

> I train four days each week. Give me a high-protein breakfast under 500 calories.

The chat request requires a session ID matching `chat_` plus 16 lowercase hexadecimal characters, such as `chat_0123456789abcdef`; the frontend normally creates this automatically.

## 6. Verify authenticated API-to-agent delegation

1. In <http://localhost:8000/docs>, use `POST /api/auth/register` if needed, then `POST /api/auth/login`.
2. Copy `access_token` from the login response.
3. Click **Authorize** and enter `Bearer <access_token>`.
4. Call an authenticated public Nutrition route, such as `GET /api/nutrition/profile` or `PUT /api/nutrition/profile`.
5. Watch the Terminal 2 and Terminal 3 logs while issuing the request.

Success criteria:

- Browser traffic goes only to `localhost:8000/api`.
- The main API makes the internal request to `localhost:8003`.
- The internal token is never present in browser DevTools, frontend source, or public responses.
- The Nutrition Agent logs show the private request without sensitive request contents or tokens.

## 7. Test failure behavior

Stop the Nutrition Agent in Terminal 2 with `Ctrl+C`.

- Send a nutrition chat request through the frontend or `POST /api/chat`. The chat path should fall back to the local nutrition specialist.
- Call `GET /api/nutrition/profile` in Swagger. It should safely return HTTP `503` with `DEPENDENCY_UNAVAILABLE`; it must not expose the private service URL, token, or raw upstream error.

Restart Terminal 2's Nutrition Agent command and repeat its readiness check.

## 8. Stop local services

Use `Ctrl+C` in the three application terminals (Nutrition Agent, main API, and frontend). PostgreSQL is managed separately and is not stopped by these commands.

## Fast troubleshooting

| Symptom | Check |
| --- | --- |
| Nutrition Agent readiness is `503` | Confirm local PostgreSQL is running, `DATABASE_URL` and `DATABASE_SCHEMA` match the migrated database, and the internal token is non-empty. |
| Main API readiness is `503` | Run `uv run python -m app.db.migrate --check`; confirm its token is set and, when service use is enabled, the Nutrition Agent URL and rollout percentage are valid. |
| Chat does not reach the agent | Confirm Terminal 3 has `USE_NUTRITION_AGENT_SERVICE=true` and `NUTRITION_AGENT_ROLLOUT_PERCENT=100`, then restart the main API. |
| Browser CORS error | Confirm frontend runs at `http://localhost:5174` and `ALLOWED_ORIGINS` includes that exact origin; restart the main API after changing `.env`. |
| Nutrition Agent imports the wrong `app` | Start it only after `Set-Location C:\dev\multi-agent-coach\services\nutrition_agent`. |
| Database login failure | Correct the password, host, or database in `DATABASE_URL`; ensure the named database already exists. |
| `No module named pip` in `services\nutrition_agent\.venv` | This is normal for an environment created by `uv venv` without `--seed`. Install dependencies with `uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt`; do not use `python -m pip`. |
| `asyncpg` or `pydantic-core` tries to build, or requests Microsoft C++ Build Tools | Confirm `\.venv\Scripts\python.exe --version` reports Python 3.12, delete the service-local `.venv` if it does not, then recreate it with `uv venv --python 3.12 .venv`. These pinned service dependencies do not have compatible wheels for the root Python 3.14 environment. |
| A valid IANA timezone, such as `Asia/Singapore`, is rejected | Reinstall the service requirements with `uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt`, confirm the timezone command in step 3 prints `Asia/Singapore`, then restart the Nutrition Agent on port `8003`. |