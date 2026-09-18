# Head Coach Agent service

Private FastAPI microservice that chooses the next specialist (Alex, Sam, or Jordan).
The gateway keeps using `agents/orchestrator.py`; that module calls this image when
`USE_HEAD_COACH_SERVICE=true`.

## Run locally (no Docker)

From the repository root:

```powershell
$env:HEAD_COACH_SERVICE_MODE = 'true'
$env:INTERNAL_SERVICE_TOKEN = 'local-dev-recovery-token'
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn services.head_coach.app.main:app --reload --port 8002
```

Health check: `GET http://localhost:8002/health`

Routing requires header `X-Internal-Service-Token`.
