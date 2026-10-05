# OWASP ZAP baseline scan

The [OWASP ZAP Baseline](../.github/workflows/zap-dast-ci.yml) GitHub Actions
workflow starts an isolated Docker Compose copy of the app and scans the public
frontend at `http://frontend:5174/` and API documentation at
`http://api:8000/docs`. It runs when a pull request is merged into `main`, or
manually through **Actions → OWASP ZAP Baseline → Run workflow**. Direct pushes
to `main` do not trigger it.

Open the Actions run and download the **zap-baseline-reports** artifact. It
contains `frontend.html`, `frontend.json`, `api.html`, and `api.json`. Reports
are generated in `zap-reports/` on the runner and are not committed to Git.

This is a passive, unauthenticated baseline scan: it spiders each target for
one minute without active attack payloads. It does not scan signed-in pages
such as Nutrition Today, call protected API endpoints, or scan the deployed EC2
site. Those require a separate authenticated scan or deployment target.

ZAP does not need an OpenAI key. The workflow supplies a placeholder value so
the application can start; it does not make LLM requests. The `-I` option
keeps findings classified as warnings from failing the job while they are
triaged. Startup failures and missing reports still fail the job. Once the
first reports are reviewed, remove `-I` or add a ZAP rules configuration to
make selected alerts fail CI.
