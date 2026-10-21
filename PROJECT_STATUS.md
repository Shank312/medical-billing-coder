# Project Status

Last updated: Phase 1 completion.

| Phase | Scope | Status |
|---|---|---|
| **1 — Secure platform core** | Tenant isolation, RBAC, Argon2 auth + refresh rotation/reuse detection, TOTP MFA, hash-chained audit, redacted logging, rate limiting, Alembic migrations, Next.js shell + login, Docker, docs, pytest | ✅ **Complete** |
| 2 — AI coding workflow | Provider-agnostic LLM interface + DeepSeek adapter, structured-output validation, versioned code sets, deterministic ICD-10/CPT/HCPCS validation | Planned |
| 3 — Product workspace UI | Split-screen note/coding review, editable suggestions, approval flow, templates, review queues, search, notifications | Planned |
| 4 — Documents & async jobs | Upload validation, object storage, malware-scan hook, PDF/CSV batch, Celery+Redis, transcription, CSV/XLSX export, PDF summary | Planned |
| 5 — SaaS & durable memory | Subscriptions, usage ledger, Stripe + webhooks, tenant-scoped memory (pgvector optional) | Planned |
| 6 — Interop & hardening | FHIR export, dashboards, usage metrics, Playwright e2e, security hardening | Planned |

## Phase 1 — delivered

- **Backend** — FastAPI app factory; `core/` (config, security, crypto, errors,
  logging, rate limiting, time), `models/`, `repositories/` (tenant-scoped),
  `services/`, `api/v1/`; Alembic migration `71a37da41773_initial_schema`.
- **Security** — Argon2id password hashing; short-lived JWT access tokens; hashed
  rotating refresh tokens with reuse detection (family revocation); TOTP MFA with
  Fernet-encrypted secrets; deny-by-default RBAC (owner/admin/provider/coder/
  biller/auditor/read-only); tenant isolation returning 404 for cross-tenant
  access; append-only HMAC-chained audit with tamper detection; redacted logging;
  shared rate limiter; normalized error contract.
- **Frontend** — Next.js App Router + TypeScript + Tailwind; premium login screen
  with loading/error states and accessible components; typed API client;
  dashboard placeholder.
- **Infra** — backend/frontend Dockerfiles, `infra/docker-compose.yml` (Postgres,
  Redis, backend, frontend), `.env.example` files.
- **Docs** — README, ARCHITECTURE, SECURITY, DATA_MODEL, API, COMPLIANCE_CHECKLIST.

## Verification (Phase 1)

- ✅ 39 backend tests pass (auth, RBAC, tenant isolation, audit/tamper, redaction, rate limit, health, config).
- ✅ Backend lint clean (`ruff check app tests`).
- ✅ Alembic `upgrade head` → `check` (no drift) → `downgrade base` → re-`upgrade`.
- ✅ Frontend lint (no warnings/errors), typecheck, and production build all pass (Next.js 14.2.35).
- ⚠️ PostgreSQL migration verification not run on this machine (no PostgreSQL/Docker available).
- ⚠️ `docker compose config` not validated on this machine (Docker not installed).

## Known limitations (Phase 1)

- Invited members are created as inactive provisional accounts with no password;
  a real invitation/claim flow lands in a later phase.
- The rate limiter is process-local; a multi-worker deployment needs a shared
  store (Redis) — the interface is swap-ready.
- Audit chain integrity assumes the confidentiality of `AUDIT_HMAC_KEY` (see
  SECURITY.md for the exact guarantee and its limits).
- AI-provider transmission is disabled; no clinical coding, document processing,
  Stripe, or application memory exists yet.
- `next@^14.2.21` is pinned to the patched 14.2.x line; upgrade to a supported
  major before production.
