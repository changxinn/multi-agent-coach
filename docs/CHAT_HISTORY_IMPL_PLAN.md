# Durable Chat History and Nutrition Context — Implementation Plan

## 1. Objective

Replace process-local chat sessions as the source of truth with durable,
authorized PostgreSQL-backed chat history. An authenticated user must be able
to continue an authorized conversation after an API restart or worker change,
and the Nutrition specialist must receive relevant, bounded prior context when
the main API routes a turn to it.

PostgreSQL is the canonical store for session ownership, transcript ordering,
summaries, and retention state. Redis is explicitly not required for this
phase and must never become the authority for transcripts or authorization.

## Implementation Tracker

Update these tasks as implementation is completed and validated. Detailed
requirements and acceptance evidence remain in the sections below.

- [x] Approve product, lifecycle, privacy, context, and rate-limit decisions.
- [x] Add and validate immutable PostgreSQL chat-history migration.
- [x] Implement durable authorized repository and chat-history service.
- [x] Update session/chat API contracts, ownership authorization, and input limits.
- [x] Replace in-memory session history as the canonical transcript source.
- [x] Implement bounded trusted context and summary lifecycle.
- [x] Integrate API-assembled context with Nutrition only.
- [x] Implement Nutrition-safe private-service failure handling.
- [x] Add configuration and operational documentation; no expiry job is required.
- [x] Add focused unit, authorization, and safe-fallback coverage.
- [ ] Add PostgreSQL integration coverage and complete final validation.

## 2. Scope

### In scope

- Durable PostgreSQL session ownership, lifecycle, and ordered message storage.
- Main-API authorization before every session read, write, clear, delete, or
  context assembly operation.
- Server-generated session identifiers only.
- Server-assembled compact context using trusted rolling summaries,
  post-summary messages, and allowlisted structured facts.
- Nutrition-Agent request-contract support for API-assembled context.
- Nutrition-safe behavior when the private Nutrition service fails.
- Chat payload/message limits, metadata sanitization, and a rate-limiting
  design compatible with a later Redis deployment.
- Migration, repository, route/schema, service, documentation, and test work.

### Explicitly deferred

- **Recovery-Agent chat-context integration, request contract changes, fallback
  changes, and Recovery-specific tests.** The shared history/context design
  will remain agent-neutral so Recovery can adopt it later, but this phase must
  not change Recovery behavior.
- Redis transcript storage, ownership checks, or required runtime dependency.
- Client-supplied chat history, client-created system/summary roles, and
  client-selected specialist context.
- Unlimited raw transcript forwarding to an LLM or private service.
- Automatic restoration of deleted sessions.
- A full compliance program beyond the product decisions and controls listed
  below.

## 3. Product and Compliance Decisions Required Before Coding

The following decisions affect schema, API behavior, cleanup jobs, and tests.
They must be approved and recorded before implementation uses irreversible
defaults.

| Decision | Choices to resolve | Affected behavior |
| --- | --- | --- |
| Session expiry | **No automatic expiry**; session remains active until explicitly soft-deleted | no expiry cleanup or restoration flow |
| Transcript retention | **Retain until explicit deletion** | no automatic transcript purge initially; protect backups |
| Expired session restoration | **Never restore** | deleted IDs are never reopened or rebound |
| Deletion model | **Soft delete** | set `deleted_at`; hide/reject deleted sessions; no automatic purge initially |
| Privacy classification | **Sensitive personal, health-adjacent data** | least-privilege access, TLS, encrypted storage/backups, no-content logging |
| Encryption | **Recommended initial approach**: TLS plus managed database/storage and backup encryption at rest | application-level field encryption is designed for but deferred |
| User rights | **Authenticated owner export, deletion, and profile/account correction** | owner-only export/delete; transcript messages remain immutable |
| Summary cadence | **Every 10 completed turns**, configurable | rolling-summary freshness and context compaction |
| Context budget | **No independent character/token cap initially** | downstream receives one rolling summary plus post-summary messages only |
| Rate limits | **No application-level limit initially** | retain authentication and request/message-size protections; defer `429` policy |

### Approval checklist

- [x] Approve no-automatic-session-expiry policy.
- [x] Approve retention until explicit deletion, with no automatic purge initially.
- [x] Approve no restoration for deleted sessions.
- [x] Approve soft deletion with no automatic purge/anonymization initially.
- [x] Approve sensitive personal, health-adjacent classification; TLS and managed database/storage and backup encryption at rest; no-content logging.
- [x] Approve authenticated-owner export/deletion and profile/account correction; persisted transcript messages are immutable.
- [x] Approve configurable rolling summaries every 10 completed turns; retain raw messages if summarization fails and retry later.
- [x] Approve a rolling summary plus post-summary messages as Nutrition context, with no independent character/token cap initially.
- [x] Approve no application-level rate limit initially; retain authentication and request/message-size protections.

### Approved initial policy

- Sessions do not automatically expire; an active session remains usable until
  its owner explicitly soft-deletes it.
- Retain transcripts until explicit deletion. Do not automatically purge
  soft-deleted sessions or messages in the initial release.
- A deleted session is never restored, reopened, or rebound by standard APIs.
- Treat chat history and profile-derived Nutrition context as sensitive
  personal, health-adjacent data. Require TLS in deployed environments, managed
  database/storage and backup encryption at rest, and no transcript/summary/
  sensitive-fact logging. Application-level field encryption is deferred, but
  repository/storage interfaces must not preclude adding it later.
- An authenticated owner can export and soft-delete their data and correct
  profile/account data. Persisted user and assistant transcript messages are
  immutable; deleting the owning session is the remedy for an incorrect chat.
- Generate a rolling trusted summary after every 10 completed turns using
  `CHAT_SUMMARY_TURN_INTERVAL=10`. The value is configurable.
- Send Nutrition one latest rolling summary plus at most 24 raw messages after
  `summary_through_sequence`. All original messages remain stored.
- Do not apply application-level rate limits initially. Continue to enforce
  authentication plus public request and message-size limits.

## 4. Current Project Constraints

- `C:\dev\multi-agent-coach\app\services\session_manager.py` remains only as a
  compatibility type for legacy callers. Durable routes and orchestration no
  longer read or write its process-local/S3 transcript behavior.
- `C:\dev\multi-agent-coach\app\api\routes\session.py` currently permits a
  client-provided session ID during creation. This must be removed: unknown,
  deleted, or foreign IDs must never be rebound to a requester.
- The main API uses SQLAlchemy async sessions from
  `C:\dev\multi-agent-coach\app\db\database.py`.
- Schema changes are immutable SQL migrations in
  `C:\dev\multi-agent-coach\app\db\migrations`. API startup validates schema
  compatibility and must not run DDL.
- The Nutrition private service has deterministic safety assessment logic.
  Context additions and service-failure behavior must preserve that as the
  safety authority.
- Redis is optional in `C:\dev\multi-agent-coach\docker-compose.yml`; no
  active Redis client dependency is needed for the canonical-history phase.

## 5. Target Architecture

```text
Browser
  -> Main API
      -> authenticate JWT
      -> validate one current user message and request limits
      -> create or authorize durable PostgreSQL session
      -> persist user message
      -> build rolling-summary and post-summary context
      -> route selected specialist
      -> invoke Nutrition service or nutrition-safe fallback
      -> validate/sanitize assistant response
      -> persist assistant response and update activity/summary state
      -> return response

PostgreSQL
  -> canonical ownership, lifecycle, ordered messages, and trusted summaries

Redis (future optional layer)
  -> rate limiting, distributed turn locks, derived-context cache, streaming
     coordination; never canonical transcripts or ownership
```

### Trust boundaries

1. A client supplies only its current user message and a server-issued session
   identifier.
2. The main API authenticates, authorizes, persists, assembles context, and
   routes specialists.
3. Nutrition receives only API-assembled compact context and the private data
   necessary for its established contract.
4. Only server code writes message sequencing, trusted summaries, specialist
   attribution, timestamps, and sanitized metadata.
5. Nutrition deterministic safety policy controls safety status, restrictions,
   escalation, and the allowed presentation boundary.

## 6. PostgreSQL Schema and Migration

Create the next immutable migration under:

- `C:\dev\multi-agent-coach\app\db\migrations\`

At implementation time, confirm the latest migration number. Based on the
current repository it is expected to be:

- `011_create_chat_history_tables.sql`

### `chat_sessions`

| Column | Purpose |
| --- | --- |
| `id` | server-generated opaque public session ID; primary key |
| `user_id` | immutable owner; foreign key to `users(id)` |
| `created_at` | UTC creation timestamp |
| `last_activity_at` | latest accepted/completed activity timestamp |
| `expires_at` | omitted for the initial no-automatic-expiry policy |
| `deleted_at` | soft-delete marker if that policy is selected |
| `summary` | trusted server-generated summary, never client input |
| `summary_version` | monotonic summary revision for invalidation/concurrency |
| `summary_through_sequence` | latest message sequence represented in summary |
| `metadata` | bounded, allowlisted server-controlled JSON metadata |

Constraints and indexes:

- Foreign key to the main `users` table.
- `summary_version >= 0` and `summary_through_sequence >= 0`.
- Index `(user_id, last_activity_at DESC)`.
- An active-session partial index excluding soft-deleted sessions.
- No mutable owner field and no client-selected-ID creation path.

### `chat_messages`

| Column | Purpose |
| --- | --- |
| `id` | internal primary key |
| `session_id` | owning session |
| `sequence_number` | monotonic order within session |
| `role` | restricted to persisted `user` or `assistant` |
| `agent_name` | nullable controlled assistant attribution |
| `content` | validated message text |
| `metadata` | bounded, sanitized server-controlled JSON metadata |
| `created_at` | UTC creation timestamp |

Constraints and indexes:

- Foreign key to `chat_sessions(id)` consistent with approved deletion policy.
- Unique `(session_id, sequence_number)`.
- Check constraints for allowed roles and positive sequence numbers.
- Index `(session_id, sequence_number ASC)`.
- Database content-length constraint matching the public API maximum.
- Never persist prompts, credentials, headers, service tokens, raw provider
  payloads, stack traces, or chain-of-thought.

### Migration validation

Update compatible-schema validation in
`C:\dev\multi-agent-coach\app\db\migrate.py` for the required history tables,
columns, constraints, and indexes. Continue using:

```powershell
uv run python -m app.db.migrate
uv run python -m app.db.migrate --check
```

Runtime startup must only validate; it must never create or alter history
tables.

## 7. Repository and Domain Service

### New modules

Create:

- `C:\dev\multi-agent-coach\app\db\repositories\chat_history_repo.py`
- `C:\dev\multi-agent-coach\app\services\chat_history_service.py`
- `C:\dev\multi-agent-coach\app\services\chat_context_builder.py`

Follow the existing main-API SQLAlchemy async-session conventions.

### Repository responsibilities

- Insert server-generated sessions.
- Fetch sessions without implicit creation.
- Read messages in deterministic sequence order.
- Allocate and append ordered messages with database-enforced uniqueness.
- Update activity, summary, clear, and soft-deletion state.
- Return post-summary message windows in deterministic sequence order.
- Do not select automatic purge candidates under the initial retain-until-
  deletion policy.

### Domain-service responsibilities

- Generate secure opaque session IDs and eliminate client control of creation
  identifiers.
- Authorize session owner for every operation, including export.
- Reject unknown, deleted, and foreign IDs; never recreate or rebind them.
- Normalize domain outcomes so routes consistently apply the approved
  `403`/`404` information-disclosure policy.
- Execute durable chat turns and expose compatibility adapters only temporarily
  where legacy callers need migration from `SessionManager`.
- Retire in-memory session state as the source of truth.

### Concurrency and retry contract

Define and test the following before final implementation:

- Concurrent turns cannot allocate duplicate sequence numbers or reorder a
  transcript.
- Use short-lived row locking/transactional sequence allocation. Do not keep a
  database transaction open across an unbounded model or service call unless
  tested and explicitly justified.
- If user-message persistence succeeds but assistant generation fails, retain
  the accepted user message and record only controlled failure state if needed;
  never fabricate an assistant response.
- Determine whether public clients require idempotency keys for retry-safe turn
  submission. If not implemented, document retry semantics explicitly.

## 8. API Contract and Validation

Update:

- `C:\dev\multi-agent-coach\app\api\routes\chat.py`
- `C:\dev\multi-agent-coach\app\api\routes\session.py`
- `C:\dev\multi-agent-coach\app\api\schemas\chat.py`
- `C:\dev\multi-agent-coach\app\api\schemas\session.py`

### Session creation

- `POST /session` creates a server-generated ID only.
- Remove or deprecate `SessionCreateRequest.session_id`.
- Do not accept client profile data as source-of-truth session context; fetch
  canonical profile facts server-side.

### Chat submission

Accept exactly one current user message with an authorized server-issued
session ID. Reject:

- missing, empty, whitespace-only, or oversized content;
- multiple arbitrary client history messages;
- `system`, `summary`, `tool`, or client-supplied assistant roles;
- malformed session IDs and unrecognized client metadata;
- bodies exceeding configured public endpoint limits.

Define consistent `400`, `403`, `404`, `409`, `413`, `422`, `429`, and `503`
semantics without disclosing ownership details unnecessarily.

### Session lifecycle endpoints

- Read PostgreSQL history with deterministic pagination/bounds.
- Authorize before returning session metadata, messages, or exports.
- Ensure clear/delete cannot affect a foreign session.
- Define whether clear creates a summary reset/auditable marker.
- Implement deleted-session rejection without recreating or rebinding IDs.
- Provide authenticated-owner export of owned session/transcript data using a
  documented safe response format.
- Keep persisted user and assistant messages immutable; profile/account
  correction uses existing profile/account APIs, and deleting an owned session
  is the remedy for an incorrect transcript.

## 9. Shared Rolling Context Builder

`ChatContextBuilder` is the only mechanism allowed to prepare conversation
history for specialist calls. It is agent-neutral, but this implementation
integrates it with Nutrition only.

### Inputs

- Authorized durable session.
- Trusted server-generated summary.
- Recent ordered persisted messages.
- Selected agent name.
- Server-fetched fitness profile.
- Allowlisted Nutrition structured facts when relevant and permitted.
- The configured summary cadence and current summary boundary.

### Output

An internal structured context containing:

1. One latest trusted rolling summary, if one exists.
2. Every ordered persisted `user`/`assistant` message after
   `summary_through_sequence`.
3. Minimal allowlisted facts relevant to Nutrition.
4. Non-sensitive provenance/version metrics for observability.

### Rules

- Preserve chronological order for post-summary messages.
- Persist all valid history. For Nutrition, send only the latest rolling summary
  and at most 24 chronological messages after its `summary_through_sequence`.
- Never elevate client text or persisted content to a system instruction.
- Never accept a client-created summary or system role.
- Avoid raw content in logs.
- Omit/redact fields prohibited by approved privacy policy.

### Summary strategy

Implement the approved rolling-summary behavior:

- Trigger after `CHAT_SUMMARY_TURN_INTERVAL` completed turns (initial value:
  10). A completed turn is one persisted user message and its persisted
  assistant response.
- Generate one concise factual rolling summary from the previous trusted
  summary plus the next completed-turn block.
- Validate length and safety requirements before persisting it.
- Advance `summary_through_sequence` to the final message covered only after the
  trusted LLM returns a valid summary. Replace the preceding summary rather than
  accumulating multiple summary records in downstream context.
- For example, with 22 persisted message records, the summary covers records
  1–20 and Nutrition receives that one rolling summary plus raw records 21–22.
- If summarization fails, retain all history and send the prior summary plus all
  post-summary raw messages; retry later. Do not accept a client-created
  replacement summary or block an otherwise safe reply solely because a summary
  is absent.

## 10. Nutrition Integration and Safe Failure Behavior

Update the relevant main-API orchestration and Nutrition client paths:

- `C:\dev\multi-agent-coach\app\services\agent_service.py`
- `C:\dev\multi-agent-coach\app\services\agent_orchestrator.py`
- `C:\dev\multi-agent-coach\app\services\nutrition_agent_client.py`
- Nutrition service schemas/routes only where required for an explicit
  API-assembled rolling-summary and post-summary-message context contract.

### Contract direction

- Main API owns authentication, session authorization, transcript selection,
  and context assembly.
- Nutrition receives the current user message separately from the one rolling
  summary plus post-summary chat context and deterministic safety context.
- Context contract changes must be versioned or backward-compatible during
  rollout.
- Nutrition deterministic assessment remains the authority for risk,
  escalation, restrictions, and allowed response presentation.

### Mandatory nutrition failure behavior

On Nutrition timeout, connection error, malformed response, or 5xx:

- Do **not** send nutrition/medical-risk chat directly to an unguarded generic
  local LLM.
- Return a deterministic nutrition-safe/referral response, **or** invoke a
  local path protected by identical deterministic nutrition guards before any
  constrained presentation generation.
- Log only non-sensitive failure category, selected agent, and correlation
  metadata.

## 11. Configuration, Operations, and Redis Boundary

Update:

- `C:\dev\multi-agent-coach\app\config.py`
- `C:\dev\multi-agent-coach\.env.example`
- `C:\dev\multi-agent-coach\README.md`
- relevant architecture and operations documentation.

Add validated settings after policy approval, for example:

- `CHAT_MAX_REQUEST_BYTES`
- `CHAT_MAX_MESSAGE_CHARS`
- `CHAT_SUMMARY_TURN_INTERVAL=10`
- `CHAT_SUMMARY_MAX_CHARS`

Do not add automatic expiry, retention/purge, application-level rate-limit, or
independent downstream context-budget settings in the initial release. The
summary interval must validate as a positive integer.

Do not add a Redis dependency until canonical PostgreSQL behavior is complete
and tested. A later Redis phase may cache derived recent context keyed by
session ID and summary version, provide distributed rate limiting, and provide
short-lived turn locks. Cache invalidation must occur after transcript,
summary, clear, delete, or expiry changes, and PostgreSQL must remain the safe
fallback.

## 12. Security, Privacy, and Observability

### Controls

- Authenticate before every history operation.
- Authorize ownership before transcript/context access.
- Generate IDs with cryptographically secure server-side entropy.
- Use parameterized SQL/SQLAlchemy operations.
- Strictly validate public schemas and content limits.
- Allowlist and bound persisted metadata.
- Do not log message bodies, summaries, health facts, authentication data, or
  internal-service credentials.
- Use TLS for database/internal-service communication in deployments.
- Use managed database/storage and backup encryption at rest.
- Treat chat history and profile-derived Nutrition context as sensitive
  personal, health-adjacent data; document least-privilege production and
  backup access accordingly.
- Defer application-level field encryption, while keeping repository/storage
  interfaces compatible with a later encryption layer.

### Non-sensitive observability fields

- correlation/request ID;
- safe internal session reference or hash where appropriate;
- selected agent;
- context item count, summary version, and post-summary message count;
- summary version;
- Nutrition service latency and safe-fallback category;
- persistence outcomes.

## 13. Test Plan

### Unit tests

Add focused coverage for:

- secure server-only session ID generation;
- request/session ID validation;
- owner, foreign, missing, and deleted-session outcomes;
- prevention of rebinding unknown/deleted/foreign IDs;
- ordered sequence allocation and metadata sanitization;
- rolling-summary usage, summary boundary, post-summary ordering, and
  Nutrition-specific facts;
- rejection of client-created system/summary/assistant history;
- summary version/through-sequence handling;
- authenticated-owner export; immutable transcript messages; and profile/account
  correction routed through existing profile/account APIs;
- nutrition timeout/5xx/malformed-response safe fallback;
- expected logs/metadata containing no raw transcript body.

### PostgreSQL integration tests

Use only an explicitly disposable PostgreSQL test database and existing
migration conventions. Test:

- migration application and compatible-schema validation;
- session/message survival across repository/service re-instantiation to model
  restart recovery;
- cross-user denial for read, submit, clear, and delete;
- absent IDs are not recreated/rebound;
- recovery of all persisted messages while older messages remain stored;
- one rolling summary plus post-summary raw messages without client-originated
  summaries, including the 22-record/20-record-summary scenario;
- soft-deletion, clear, retention-until-deletion, and no-restoration behavior;
- authenticated-owner transcript export and cross-user export denial;
- concurrent append sequence integrity;
- transfer of authorized relevant conversation context to Nutrition;
- Nutrition private-service failures return only safe behavior.

### Regression commands

From `C:\dev\multi-agent-coach`:

```powershell
uv run python -m app.db.migrate --check
uv run pytest -q
uv run ruff check .
```

Run database integration tests only against an explicitly configured disposable
database. Never migrate, truncate, or purge a shared development, staging, or
production database as test setup.

### Implemented limitations

- PostgreSQL is the canonical transcript store; history is retained until an
  owner clears or soft-deletes its session. Clear advances the visible/context
  boundary while retaining immutable rows; soft-delete prevents restoration.
- Summary generation is trusted server-side LLM work only. It accumulates the
  previous trusted summary with the next eligible persisted completed-turn block.
  If it fails, the prior summary and boundary remain unchanged; raw text is never
  fabricated as a substitute summary.
- The current sequence allocation assumes one active turn per session. Turn
  locks/idempotency and multi-writer concurrency controls are explicitly deferred.

## 14. Implementation Sequence

- [x] Approve and record every decision in Section 3.
- [ ] Confirm the latest migration number; add the immutable chat-history
  migration and migration/schema validation tests.
- [ ] Add repository mappings and `ChatHistoryRepository` using main API async
  SQLAlchemy conventions.
- [ ] Implement `ChatHistoryService` with durable ownership, lifecycle checks,
  ordered persistence, and bounded retrieval.
- [ ] Update session schemas/routes for server-only IDs and consistent lifecycle
  authorization.
- [ ] Replace `SessionManager` as canonical storage and remove unsafe implicit
  recreation behavior.
- [ ] Tighten chat request validation and public payload/message bounds.
- [ ] Implement `ChatContextBuilder` with the trusted rolling-summary and
  post-summary-message context contract.
- [ ] Integrate the builder into orchestration and the Nutrition request
  contract; do not change Recovery behavior.
- [ ] Make Nutrition private-service failure paths deterministic and safe.
- [ ] Add trusted summary creation/storage after base persistence works.
- [ ] Preserve the no-rate-limit initial policy and defer any Redis-backed
  distributed rate limiting to its own non-canonical follow-up if needed.
- [ ] Complete unit/integration/regression tests and run validation commands.
- [ ] Update README, environment example, architecture docs, and operational
  runbook.
- [ ] Roll out behind feature flags when legacy production sessions exist;
  monitor only non-sensitive authorization, persistence, summary, and
  Nutrition-fallback metrics before removing legacy behavior.

## 15. Acceptance Criteria

- [ ] Session IDs are server generated, durable, and owned by exactly one user.
- [ ] Restarting the API or serving from another worker retains authorized session
  state and ordered transcript history.
- [ ] Unknown, deleted, and foreign IDs cannot be recreated or rebound.
- [ ] Every persisted message has controlled role/agent attribution and a stable
  per-session sequence.
- [ ] Main API authorization and rolling context assembly occur before Nutrition is
  called.
- [ ] Nutrition receives one rolling summary plus post-summary messages, without
  forwarding multiple summaries or the complete transcript after a summary exists.
- [ ] Client input cannot inject trusted roles, summaries, system instructions, or
  server metadata.
- [ ] Nutrition service failures never bypass deterministic safety through an
  unguarded generic LLM fallback.
- [ ] Public chat has explicit input/payload limits; application-level rate
  limiting remains disabled in the initial release.
- [ ] Lifecycle, retention, deletion, restoration, and privacy behavior match
  approved product decisions.
- [ ] Migration checks, test suite, relevant PostgreSQL integration tests, and Ruff
  pass in their intended environments.
- [ ] Any later Redis outage cannot lose canonical transcripts or weaken session
  ownership authorization.

## 16. Deferred Recovery Follow-Up

When Recovery work is prioritized, reuse `ChatContextBuilder` and the
canonical PostgreSQL history service. Add Recovery-specific context fields and
private-contract changes only after its deterministic assessment and fallback
paths are reviewed. That follow-up must independently ensure Recovery failures
cannot bypass its deterministic safety assessment.