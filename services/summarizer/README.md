# Summarizer Agent service

Private FastAPI microservice that writes the session recap. The gateway keeps
calling `agents/summarizer.py`; that module calls this image when
`USE_SUMMARIZER_SERVICE=true`.

## Run locally (no Docker)

From the repository root:

```powershell
$env:SUMMARIZER_SERVICE_MODE = 'true'
$env:INTERNAL_SERVICE_TOKEN = 'local-dev-recovery-token'
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn services.summarizer.app.main:app --reload --port 8003
```

Health check: `GET http://localhost:8003/health`
