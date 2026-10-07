# Training Agent

Private FastAPI service that owns exercise guidance, versioned programs, workout logs,
progress signals, adaptations, and dashboard daily recommendations. It accepts requests
only from the main API via `X-Internal-Service-Token` and owns `trainingdb` exclusively.

Recovery status is supplied by the main API from the authoritative Recovery Agent. The
service independently enforces `red`/`escalate` no-training gating, amber RPE 6–7 with
reduced volume, and conservative output when no assessment is available.

`data/user_data.json` is intentionally not imported: it has no attributable user identity.
Legacy main-database recommendations remain readable only through the gateway fallback
during cutover.