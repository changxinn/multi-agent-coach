# Fitness coach DeepEval evaluations

This suite tests the real Head Coach and Summarizer HTTP services. It covers
specialist routing (including conversation context), clarification, medical
escalation, blocked content, prompt injection, and session/daily summary quality.
It does not exercise the authenticated chat API, database writes, or specialist
coaching responses. Existing `tests/` remain the fast offline unit suite.

Exact fields and formatting use normal pytest assertions. Safety wording and
summary quality use DeepEval GEval with a minimum score of 0.8. The judge defaults
to `gpt-4.1-mini`; set `DEEPEVAL_JUDGE_MODEL` to change it. Application models remain
configured by Docker Compose. Both application and judge calls use OpenAI credits.
DeepEval is pinned to the locally verified 3.9.9 API.

## GitHub Actions setup

1. Add `OPENAI_API_KEY` under repository Settings > Secrets and variables > Actions.
2. Optionally add the Actions variable `DEEPEVAL_JUDGE_MODEL`.
3. Commit and push the workflow and this directory. Relevant pushes and PRs to
   `main`/`master` run it; you can also select Actions > DeepEval Tests > Run workflow.

Fork and Dependabot PRs skip the live job because secrets are unavailable. Missing
keys on eligible runs fail with an actionable error. Results are uploaded as the
`deepeval-results` artifact, including failures. All cases run in one pytest command
so a failing case does not skip the other suites. The DeepEval pytest plugin and
`assert_test` execute the evaluations; using pytest directly also produces JUnit XML.

## Run locally (PowerShell, from repository root)

```powershell
python -m pip install -r deepeval-tests/requirements.txt
$env:OPENAI_API_KEY = '<your key>'
$env:INTERNAL_SERVICE_TOKEN = 'local-dev-recovery-token'
$env:DEEPEVAL_TELEMETRY_OPT_OUT = 'YES'
docker compose up --build -d --wait --wait-timeout 180 head-coach summarizer
python -m pytest deepeval-tests -v --junitxml=deepeval-tests/results/junit.xml
docker compose stop head-coach summarizer
```

Use `HEAD_COACH_URL` and `SUMMARIZER_URL` to target other service addresses.
The token must match the running services. API calls have a 180-second timeout;
HTTP and model-judge errors fail the run. Routing cases require the LLM routing
reason, and summary tests reject known fallback text, so model outages do not
silently pass those live checks. Scores can vary between runs; investigate the
reported reasons before changing a threshold.

Collection is offline: `python -m pytest deepeval-tests --collect-only -q`.
