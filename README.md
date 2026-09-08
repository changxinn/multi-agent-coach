# Multi-Agent Fitness Coach — Local Development

Multi-Agent Fitness Coach is a FastAPI application with a React frontend, PostgreSQL persistence, and optional private Recovery and Nutrition Agent services.

This guide covers running and testing the application locally. For the containerized main API and agent stack, see [README-to-be.md](README-to-be.md).

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (recommended for Python commands)
- PostgreSQL 16+ running locally
- Node.js 18+ for the frontend

Create the database named in `DATABASE_URL` before applying migrations. The application and migration runner do not create the PostgreSQL database itself.

## 1. Configure the backend

From the repository root:

```powershell
Copy-Item .env.example .env
uv sync --group dev
```

Update `C:\dev\multi-agent-coach\.env` with values appropriate for your local PostgreSQL instance:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/systemdb
DATABASE_SCHEMA=systemdb
JWT_SECRET_KEY=replace-with-a-local-secret-at-least-32-characters
OPENAI_API_KEY=your-key-if-required-by-your-chat-configuration
FRONTEND_URL=http://localhost:5174
ALLOWED_ORIGINS=http://localhost:5174,http://localhost:3000
```

Confirm PostgreSQL is listening and the configured database exists before continuing. On Windows:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5432
```

## 2. Apply migrations

Migrations are explicit and must run before starting the API:

```powershell
uv run python -m app.db.migrate
uv run python -m app.db.migrate --check
```

The first command updates the configured database and records applied versions in the migration ledger. The `--check` command is read-only. Run these only against a database designated for this application.

Normal API startup validates the database, ledger, and schema; it does **not** create the database, apply migrations, create tables, or seed users.

## 3. Start the main API

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

Verify the local API in a separate terminal or browser:

```powershell
Invoke-WebRequest http://localhost:8000/health/live
Invoke-WebRequest http://localhost:8000/health/ready
```

- API documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Readiness: <http://localhost:8000/health/ready>

## 4. Start the frontend

In a separate terminal:

```powershell
Set-Location C:\dev\multi-agent-coach\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

The frontend defaults to `VITE_API_BASE_URL=http://localhost:8000/api` and is available at <http://localhost:5174>.

## 5. Test the local application

### Automated tests

From `C:\dev\multi-agent-coach`:

```powershell
uv run pytest -q
uv run ruff check .
```

PostgreSQL-backed Nutrition integration tests require an explicitly disposable database named `nutrition_test`; configure `NUTRITION_TEST_DATABASE_URL` as documented in `.env.example` before running them.

### Manual API smoke test

1. Open <http://localhost:8000/docs>.
2. Register a user with `POST /api/auth/register`.
3. Log in with `POST /api/auth/login` and copy the returned access token.
4. Click **Authorize** and enter `Bearer <access_token>`.
5. Call an authenticated endpoint such as `GET /api/nutrition/profile` or send a chat request through `POST /api/chat`.

## Optional: run local private agents

Private agents are optional. The main API uses its local fallback behavior unless the corresponding service flag is enabled. Start local PostgreSQL, apply migrations, and start the main API as described above before enabling an agent.

Browsers must communicate only with `http://localhost:8000/api`. Do not expose agent ports through browser-facing configuration or place internal-service tokens in frontend `VITE_*` variables.

### Nutrition Agent

The Nutrition Agent provides nutrition profiles, meal logs, targets, meal planning, food lookup, and nutrition-specific chat assistance. Configure the main API in `.env`:

```env
USE_NUTRITION_AGENT_SERVICE=true
NUTRITION_AGENT_URL=http://localhost:8003
NUTRITION_AGENT_ROLLOUT_PERCENT=100
NUTRITION_INTERNAL_SERVICE_TOKEN=replace-with-a-server-only-token
NUTRITION_LLM_ENABLED=false
```

The agent listens privately on port `8003`. Follow [docs/nutrition_agent/LOCAL-NO-DOCKER-VALIDATION.md](docs/nutrition_agent/LOCAL-NO-DOCKER-VALIDATION.md) for its CPython 3.12 service-local environment, startup commands, health and readiness checks, main-API delegation configuration, and end-to-end validation.

### Recovery Agent

The Recovery Agent provides sleep, fatigue, soreness, stress, and recovery assessments. Configure the main API in `.env`:

```env
USE_RECOVERY_AGENT_SERVICE=true
RECOVERY_AGENT_URL=http://localhost:8001
INTERNAL_SERVICE_TOKEN=replace-with-a-server-only-token
```

In a separate terminal, install and start the Recovery Agent with the same database and internal token values used by the main API:

```powershell
Set-Location C:\dev\multi-agent-coach\services\recovery_agent
python -m pip install -r requirements-dev.txt
$env:DATABASE_URL = 'postgresql://postgres:YOUR_PASSWORD@localhost:5432/systemdb'
$env:INTERNAL_SERVICE_TOKEN = 'replace-with-a-server-only-token'
python -m uvicorn app.main:app --reload --port 8001
```

Verify its public health endpoint from another terminal:

```powershell
Invoke-RestMethod http://localhost:8001/health
```

The Recovery Agent listens privately on port `8001`; all non-health endpoints require `X-Internal-Service-Token`. See [services/recovery_agent/README.md](services/recovery_agent/README.md) for recovery request examples, tests, and optional LLM-response configuration.

### Future private agents

When adding another specialist service, document it in this section with:

1. Its purpose and the local port it uses.
2. Its `USE_<AGENT>_SERVICE` flag, URL, and server-only token configuration.
3. Local installation and startup commands.
4. Its health/readiness check and a link to its detailed validation runbook.
5. A statement that browsers access it only through the main API.

## Local troubleshooting

### Database or schema readiness fails

1. Confirm local PostgreSQL is running and that `DATABASE_URL` points to the intended database.
2. Apply and validate migrations:

   ```powershell
   uv run python -m app.db.migrate
   uv run python -m app.db.migrate --check
   ```

3. Restart the API after changing `.env`.

### Port 8000 is already in use

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Or run the API on another port:

```powershell
uv run uvicorn app.main:app --reload --port 8001
```

### Admin user needed

Admin seeding is an explicit operation after migrations. Configure `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, and `SEED_ADMIN_NAME` in `.env`, then run:

```powershell
uv run python -c "from app.db.seed import seed_admin_user; from app.db.database import AsyncSessionLocal; import asyncio; asyncio.run(seed_admin_user(AsyncSessionLocal()))"
```

## Documentation

- [README-to-be.md](README-to-be.md) — containerized and AWS deployment
- [frontend/SETUP.md](frontend/SETUP.md) — frontend details
- [docs/nutrition_agent/LOCAL-NO-DOCKER-VALIDATION.md](docs/nutrition_agent/LOCAL-NO-DOCKER-VALIDATION.md) — local Nutrition Agent validation
- [docs/nutrition_agent/MIGRATION-RUNNER.md](docs/nutrition_agent/MIGRATION-RUNNER.md) — migration ledger protocol
- [docs/API-REFERENCE.md](docs/API-REFERENCE.md) — API reference
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — additional troubleshooting