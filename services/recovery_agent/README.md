# Recovery Agent service

The Recovery Agent is a private FastAPI microservice for sleep, fatigue, and recovery assessments. It persists only user-scoped recovery data in PostgreSQL and requires an internal service token for every non-health endpoint.

## Local development

Start PostgreSQL and the main API first; the main API initializes the shared `systemdb.users` table required by the Recovery Agent's foreign keys.

```powershell
docker compose up -d db
python -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd services\recovery_agent
python -m pip install -r requirements-dev.txt
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/systemdb'
$env:INTERNAL_SERVICE_TOKEN = 'local-dev-recovery-token'
python -m uvicorn app.main:app --reload --port 8001
```

Run the recovery-agent tests from the repository root:

```powershell
python -m pytest tests\test_recovery_assessment.py -q
```

Or run it with Docker Compose:

```powershell
docker compose up --build recovery-agent
```

## Example request

The user must already exist in the main API database (the seeded admin user has ID `1`).

```powershell
$headers = @{ 'X-Internal-Service-Token' = 'local-dev-recovery-token' }
$body = @{ user_id = 1; message = 'I slept 5 hours and feel exhausted'; sleep_hours = 5; sleep_quality = 2; energy = 3; soreness = 8; stress = 7 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/v1/recovery/evaluate -Headers $headers -ContentType 'application/json' -Body $body
```

`/health` is public for container health checks. All recovery data endpoints require the internal token and use parameterized database queries.

## LLM mode

Local development uses deterministic tools and policies by default, so no API credits are required. To enable the optional concise LLM response layer, set `RECOVERY_LLM_ENABLED=true`, `OPENAI_API_KEY`, and `LLM_MODEL`. The LLM only presents a response from the structured assessment; safety escalation and recovery scoring remain deterministic.
