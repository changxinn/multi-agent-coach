# Promptfoo service evaluations

Twelve live HTTP cases cover Head Coach routing (4), safety rejection (4),
session summaries (2), and daily summaries (2). The suite uses JSON and JavaScript
assertions, with no model judge. Application calls still use OpenAI credits.

Routing checks require real LLM routing rather than the heuristic fallback.
Safety cases verify rejection, flags, zero remaining turns, and refusal wording.
Summary cases check format, length, progress preservation for session summaries,
and reject known fallback output. These checks do not establish factual accuracy
or coaching quality; the DeepEval suite provides complementary judged evaluations.
The authenticated chat API, specialist services, and database writes are outside
this suite's scope.

## GitHub Actions

Add the repository Actions secret `OPENAI_API_KEY` (the same secret as DeepEval).
Push these files to `main`/`master`, or use Actions > Promptfoo Tests > Run workflow
once the workflow is on the default branch. Relevant pushes and PRs trigger it.
Fork and Dependabot PRs skip because they cannot access the secret.

CI installs Node 22 and Promptfoo 0.120.0, builds Head Coach and Summarizer, waits
for health checks, and runs every suite even if one fails. A failed assertion or
API call fails the job. Download `promptfoo-results` from the run's Artifacts to
inspect HTML reports or machine-readable JSON. Services are always torn down.
Response caching is disabled to ensure each run calls the live application.
The Promptfoo version is pinned; transitive npm dependencies are not locked.

## Local run (PowerShell, repository root)

Docker Desktop and Node.js 22 are required. Set OPENAI_API_KEY in the root `.env`
or environment for Docker Compose. INTERNAL_SERVICE_TOKEN must match Compose
(the default is shown below). No real user data is used.

```powershell
$env:INTERNAL_SERVICE_TOKEN = 'local-dev-recovery-token'
$env:PROMPTFOO_DISABLE_TELEMETRY = '1'
$env:PROMPTFOO_DISABLE_UPDATE = '1'
$env:PROMPTFOO_CONFIG_DIR = Join-Path (Get-Location) '.promptfoo'
$env:REQUEST_TIMEOUT_MS = '180000'
docker compose up --build -d --wait --wait-timeout 180 head-coach summarizer
New-Item -ItemType Directory -Force promptfoo-tests/results | Out-Null
$failed = $false
foreach ($suite in @('routing', 'safety', 'session-summary', 'daily-summary')) {
    npx --yes promptfoo@0.120.0 eval -c "promptfoo-tests/$suite.yaml" --no-cache --no-share --no-write --max-concurrency 1 --output "promptfoo-tests/results/$suite.json" "promptfoo-tests/results/$suite.html"
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}
if ($failed) { throw 'One or more Promptfoo suites failed. Check the reports.' }
```

Endpoints are localhost ports 8002 and 8003, configured in each YAML file.
When finished, optionally run `docker compose stop head-coach summarizer`.
Reports, node_modules, and cache directories are ignored by Git.
