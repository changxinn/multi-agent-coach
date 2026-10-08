# Training Agent

Private FastAPI service that owns the training domain in `trainingdb`: training goals and
preferences, workout logs and progress, exercise guidance, versioned programs,
adaptations, and dashboard daily recommendations. It accepts requests only from the Main
API through `X-Internal-Service-Token`; other agents access a bounded training-context
projection through the Main API rather than connecting to `trainingdb`.

Recovery status is supplied by the Main API from the authoritative Recovery Agent. Daily
recommendations and generated/adapted programs use the configured LLM when available.
The service independently enforces `red`/`escalate` no-training gating, amber RPE 6–7
with reduced volume, and a deterministic safe fallback for missing/invalid LLM output.

`data/user_data.json` is intentionally not imported: it has no attributable user identity.
The explicit non-microservice local-development fallback may still use the legacy Main
API recommendation store; Docker Compose enables the Training Agent and does not use it.