# Nutrition Agent Scaffold Inventory

**Status: superseded as an implementation-completion claim.** The authoritative implementation plan is `C:\dev\multi-agent-coach\docs\nutrition_agent\NUTRITION-SERVICE-IMPLEMENTATION-PLAN.md`; executable contracts are under `C:\dev\multi-agent-coach\docs\nutrition_agent\`.

The files in this directory provide an inventory of earlier Nutrition Agent scaffolding: a FastAPI application, repository, deterministic helper modules, an optional LLM layer, Docker assets, and a narrow orchestrator client integration. They are not a completed Nutrition Agent implementation and are not ready for deployment or user-facing enablement.

## Do not treat the scaffold as contract-compliant

The current scaffold predates the canonical contracts and must be replaced during implementation because it includes legacy unscoped private routes, runtime schema DDL, incomplete history/adherence behavior, response reasoning/tool traces, unsafe raw-message LLM context, broad legacy safety matching, and assessment persistence that is not limited to approved projections.

The following are planned implementation work, not completed capabilities:

- one-shot migration runner, migration ledger, and validation-only startup;
- canonical `/v1/nutrition/users/{user_id}/...` private routes and ownership-safe `/api/nutrition/...` routes;
- typed deterministic safety engine and sanitized assessment persistence;
- target versioning, meal-log CRUD, daily history/adherence, and restriction-safe meal planning; API-level idempotency is deferred to pre-production hardening;
- normalized cache-first food search with USDA resilience;
- lifespan-managed asynchronous client resilience, readiness/liveness, rate limiting, observability, and comprehensive tests.

## Current validated evidence

`C:\dev\multi-agent-coach\tests\nutrition\test_rollout.py` validates deterministic SHA-256 rollout assignment. On 2026-08-30, `python -m pytest -q tests/nutrition` passed 19 tests. This is a narrow baseline only and does not validate the Nutrition service scaffold.

## Implementation references

- API: `C:\dev\multi-agent-coach\docs\nutrition_agent\API-CONTRACT.md`
- Safety: `C:\dev\multi-agent-coach\docs\nutrition_agent\SAFETY-POLICY.md`
- Migrations: `C:\dev\multi-agent-coach\docs\nutrition_agent\MIGRATION-RUNNER.md`
- Operations: `C:\dev\multi-agent-coach\docs\nutrition_agent\OPERATIONS.md`
- Testing: `C:\dev\multi-agent-coach\docs\nutrition_agent\TESTING.md`