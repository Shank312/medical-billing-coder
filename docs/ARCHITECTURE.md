# Architecture

## Overview

Medical Billing Coder is a modular healthcare SaaS monorepo with a FastAPI
backend and a Next.js frontend. The design separates configuration, API routes,
business logic, data access, and (future) AI/document processing into distinct
layers so each can evolve and be tested independently.

```
frontend (Next.js) ──HTTP/JSON──▶ backend (FastAPI)
                                     │
                                     ├── api/       route handlers + RBAC deps
                                     ├── services/  business logic
                                     ├── repositories/  tenant-scoped data access
                                     ├── models/    SQLAlchemy ORM
                                     └── core/      config, security, logging, errors, rate limit
                                     │
                                     ▼
                              PostgreSQL (or SQLite for tests)
```

## Backend layers

| Layer | Path | Responsibility |
|---|---|---|
| API | `app/api` | Route handlers, dependency injection, RBAC, cookie/CSRF handling. No business rules. |
| Services | `app/services` | Business logic (register, login, refresh, MFA, org/member management, audit). |
| Repositories | `app/repositories` | SQLAlchemy queries. `TenantScopedRepository` enforces tenant isolation. |
| Models | `app/models` | ORM models and mixins (UUID PKs, timestamps). |
| Core | `app/core` | `config`, `security`, `crypto`, `errors`, `logging`, `rate_limit`, `time`. |
| AI | `app/ai` | Provider interface, DeepSeek + mock adapters, prompts, quality checks. |
| Schemas | `app/schemas` | Pydantic request/response contracts. |

Dependency direction is one-way: `api → services → repositories → models`. No
layer imports upward.

## Key design decisions

- **Sync SQLAlchemy 2.0.** Phase 1 uses the synchronous session to keep the code
  simple and identical across SQLite (tests) and PostgreSQL (production). Async
  can be introduced later without changing the layering.
- **Naive-UTC timestamps.** All persisted datetimes are naive UTC (see
  `app/core/time.py`) so SQLite and PostgreSQL behave identically; see
  [DATA_MODEL.md](DATA_MODEL.md).
- **UUID string primary keys** for tenant-scoped entities; **autoincrement id**
  for audit events (a `BigInteger` on PostgreSQL, `Integer` on SQLite via
  `with_variant`) so the audit chain has a monotonic order.
- **JWT access + opaque refresh.** Access tokens are short-lived signed JWTs
  carrying `sub`, `org_id`, and `roles`. Refresh tokens are 384-bit random
  strings; only their SHA-256 hash is stored, and they rotate on every use.
- **Global hash-chained audit.** A singleton `audit_chain_state` row holds the
  head hash; each event is `HMAC-SHA256(key, prev_hash + canonical_payload)`.
  Appends lock the head row (`SELECT … FOR UPDATE` on PostgreSQL; a no-op on
  SQLite, which serializes writes).
- **Tenant isolation via 404.** Cross-tenant reads/writes/updates/deletes resolve
  through the authenticated `organization_id`; a mismatch returns `404` so the
  existence of another tenant's resources is never leaked.

## Request flow (example: login)

1. `POST /api/v1/auth/login` → `app/api/v1/auth.py::login`.
2. Rate-limit dependency (`core/rate_limit`) checks the shared limiter.
3. `services/auth.py::login` verifies the Argon2 hash, resolves the membership,
   checks TOTP MFA if enabled, issues tokens, and appends an `auth.login` audit
   event — all inside one transaction.
4. The handler commits (or, on failed login, commits just the `auth.login_failed`
   audit event) and sets the HttpOnly refresh cookie.
5. The response is serialized through Pydantic schemas.

## Extensibility points (future phases)

- `core/rate_limit.py` exposes a small interface so the process-local store can be
  swapped for Redis in multi-worker deployments.
- `services/audit.py` is the single entry point for audit events.
- AI integration will live under `app/ai` behind a provider-agnostic interface
  (Phase 2); document processing under `app/documents` (Phase 4).
- Object storage and Stripe are deliberately absent in Phase 1.

## Configuration

All settings come from environment variables (and an optional `.env`) via
`pydantic-settings` (`app/core/config.py`). See `.env.example` in the backend and
root for the full key set. Secrets are never hard-coded.

## AI and coding domain (Phase 2)

The coding workflow depends only on the provider interface in `app/ai`:

- `base.py` — `AIProvider.complete(ProviderRequest) -> ProviderResponse` plus
  message/usage types.
- `deepseek.py` — OpenAI-compatible chat-completions adapter (bounded retries,
  backoff, timeouts, token accounting, sanitized errors). Sends only documented
  parameters and invents no privacy flags.
- `mock.py` — deterministic local provider so tests run with no network/API key.
- `registry.py` — name → provider class, selected from `ai_provider`.
- `prompts.py` / `schemas.py` — versioned prompt and coding-output contract.
- `quality.py` — deterministic evidence checks (offsets recomputed, hallucinated
  quotes dropped/flagged).

Transmission gates: the workflow refuses unless `ai_enabled` is true, and, for
PHI-transmitting providers, `ai_phi_approved` is true (the local mock is exempt).

Coding domain (`services/coding.py`, `services/reference_data.py`) runs
synchronously in Phase 2 (Celery arrives in Phase 4). The model returns *candidate*
suggestions; exact-evidence validation, deterministic code-set validation, and
human review are distinct, audited stages. Reference datasets are loaded — never
invented — via `import_code_set`; an unloaded code type yields the explicit
`reference_data_unavailable` status.
