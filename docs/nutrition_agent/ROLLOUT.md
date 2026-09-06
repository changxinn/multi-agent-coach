# Nutrition Agent Rollout

Status: Canonical Phase 0 rollout contract for implementation.

## Controls

- `USE_NUTRITION_AGENT_SERVICE=false` disables Nutrition Agent service calls and keeps local specialist fallback.
- `NUTRITION_AGENT_ROLLOUT_PERCENT` is required when the master switch is enabled and must be an integer `0` through `100`.
- Assignment uses SHA-256 of the authenticated numeric `user_id` encoded as UTF-8 decimal text. Interpret the first eight digest bytes as unsigned big-endian, compute modulo 100, and enable when bucket `< NUTRITION_AGENT_ROLLOUT_PERCENT`.
- Never use Python `hash()`, random assignment, request IDs, IPs, or mutable profile data.

## Rollout stages

1. `0%`: service deployed, readiness passing, no users routed.
2. Internal smoke users by explicit non-production environment only.
3. `10%`: monitor errors, latency, fallback rate, safety escalations, and cache outcomes.
4. `50%`: continue monitoring; verify no privacy/logging regressions.
5. `100%`: only after all release gates remain green.

Dedicated `/api/nutrition/*` programmatic routes are governed by auth/readiness/configuration rather than rollout bucketing unless a later decision changes this. Orchestrator/chat routing is rollout-gated.

## Pre-increase checklist

Before increasing traffic: full tests pass, readiness healthy, migration ledger compatible, secret scan pass, safety policy tests pass, USDA no-key/outage behavior verified, fallback behavior verified, docs match shipped routes, and product/privacy/safety approvals are recorded.

## Monitoring checkpoints

Track: Nutrition Agent 5xx/timeout rate, main-API fallback count, route latency p95/p99, readiness failures, rate-limit count, safety escalation count by stable code, food cache outcome, USDA circuit state, and redaction/secret-scan alerts. Metrics must not include user IDs, request IDs, raw text, secrets, or medical details.

## Rollback

Immediate rollback controls:

```env
USE_NUTRITION_AGENT_SERVICE=false
```

or:

```env
NUTRITION_AGENT_ROLLOUT_PERCENT=0
```

Rollback should not require database rollback. Forward migrations must stay compatible with disabled service behavior. After rollback, confirm orchestrator/chat uses local nutrition fallback and public programmatic mutations are disabled or return documented dependency/configuration errors.

## Release gates

- Product/privacy/safety-owner approval evidence recorded.
- USDA credential rotation/revocation attestation recorded by an authorized credential owner.
- Passing CI secret scan.
- Migration-ledger clean-install and legacy-upgrade validation complete.
- Safety-policy regression tests pass.
- Automated suite, Compose smoke, resilience smoke, and load checks pass.
- Public docs and API reference match shipped behavior.
