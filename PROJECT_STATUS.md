# Project Status

Last updated: Phase 2 completion.

| Phase | Scope | Status |
|---|---|---|
| 1 — Secure platform core | Tenant isolation, RBAC, Argon2 auth + refresh rotation/reuse detection, TOTP MFA, hash-chained audit, redacted logging, rate limiting, Alembic migrations, Next.js shell + login, Docker, docs, pytest | ✅ Complete |
| **2 — AI coding workflow** | Provider-agnostic AI interface (DeepSeek + mock, disabled-by-default with PHI approval gate), coding-domain models + migration, structured coding workflow with exact-evidence validation and hallucination rejection, deterministic code-reference validation, coding API with RBAC/tenant/idempotency | ✅ **Complete** |
| 3 — Product workspace UI | Split-screen note/coding review, editable suggestions, approval flow, templates, review queues, search, notifications | Planned |
| 4 — Documents & async jobs | Upload validation, object storage, malware-scan hook, PDF/CSV batch, Celery+Redis, transcription, CSV/XLSX export, PDF summary | Planned |
| 5 — SaaS & durable memory | Subscriptions, usage ledger, Stripe + webhooks, tenant-scoped memory (pgvector optional) | Planned |
| 6 — Interop & hardening | FHIR export, dashboards, usage metrics, Playwright e2e, security hardening | Planned |

## Phase 2 — delivered

- **AI layer (`app/ai/`)** — `base` (provider interface), `schemas` (versioned
  coding-output contract), `prompts` (versioned, note treated as untrusted data),
  `deepseek` (OpenAI-compatible adapter with bounded retries/backoff, timeouts,
  token accounting, sanitized errors), `mock` (local provider, no network),
  `registry` (provider selection), `quality` (exact-evidence validation).
- **Transmission gates** — AI is disabled by default; `ai_enabled` and, for
  PHI-transmitting providers, `ai_phi_approved` must both be set before any
  external call. The local mock needs no gate. No privacy parameters are invented.
- **Coding domain** — `encounters`, `encounter_documents` (source note stored
  separately from AI output), `coding_jobs` + `coding_attempts` (model metadata,
  no chain-of-thought), `coding_suggestions` (diagnoses/procedures/modifiers) +
  `evidence_spans`, `review_decisions`, `code_reference_sets` + `code_references`.
  Migration `9171ae3dc8b6_phase_2_coding_domain`.
- **Workflow (`services/coding.py`)** — synchronous analyze: parse+validate model
  JSON, recompute evidence offsets, drop/flag hallucinated evidence, deterministic
  code-set validation, persist job/attempt/suggestions/evidence, audit. Expected
  provider/parse failures persist a *failed* job (returned, not raised).
- **Reference validation (`services/reference_data.py`)** — import workflow +
  `valid`/`date_invalid`/`unknown`/`reference_data_unavailable` statuses. No
  authoritative dataset is invented; unloaded code types return
  `reference_data_unavailable`.
- **API** — encounter CRUD, submit-for-coding, job retrieval, suggestion review,
  and code-reference import/lookup/sets — all tenant-scoped with RBAC, pagination,
  idempotency key, rate limiting, and audit events.

## Verification (Phase 2)

- ✅ 65 backend tests pass (all Phase 1 regression + AI provider, coding workflow, reference data, coding API/tenant/RBAC/idempotency/audit/gates).
- ✅ Ruff clean (`ruff check app tests`).
- ✅ Alembic cycle: `upgrade head` → `check` (no drift) → `downgrade -1` → re-`upgrade`.
- ✅ No network / no DeepSeek key required for the test suite (mock provider).
- ⚠️ PostgreSQL migration verification not run (no PostgreSQL/Docker in this environment).

## Known limitations (Phase 2)

- Coding analysis is **synchronous**; Celery/Redis processing lands in Phase 4.
- Confidence values are **model-provided and uncalibrated** (no evaluation dataset yet).
- Modifier validation against a code set and payer-specific rules are not yet
  implemented (modifiers are persisted but not deterministically validated).
- No authoritative ICD-10/CPT/HCPCS dataset is bundled (CPT is licensed); the
  import workflow is provided and tests use clearly-labeled synthetic data.
- DeepSeek adapter is implemented to the documented OpenAI-compatible contract but
  has not been exercised against the live API (no key in this environment).
