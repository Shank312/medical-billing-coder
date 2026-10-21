# Security

This document describes the security boundaries, controls, and **known limits**
of Phase 1. It supports HIPAA-regulated workloads but **does not** claim HIPAA
compliance — that requires an independent assessment of the full production
deployment, BAAs with every service provider, and organizational controls.

## Authentication

- **Passwords** are hashed with **Argon2id** (`argon2-cffi`).
- **Access tokens** are short-lived (default 15 minutes) JWTs signed with
  `SECRET_KEY` (HS256), carrying `sub`, `org_id`, and `roles`.
- **Refresh tokens** are 384-bit random strings stored **only as SHA-256 hashes**.
  They rotate on every use; the presented token is revoked and a new one issued
  (linked via `replaced_by_id`).
- **Reuse detection**: presenting an already-revoked token revokes all of the
  user's sessions in that organization and returns `401 refresh_reuse`.
- **Session revocation**: `logout` revokes the presented token; `sessions/revoke-all`
  revokes every active refresh token for the user+organization.

## Multi-factor authentication (MFA)

- TOTP (RFC 6238) via `pyotp`, with a ±1 step clock-drift window.
- The TOTP secret is **encrypted at rest with Fernet** (AES-128-CBC + HMAC) using
  `MFA_ENCRYPTION_KEY`. The plaintext secret is shown exactly once at enrollment
  and is never logged or persisted in plaintext.
- **Key management**: `MFA_ENCRYPTION_KEY` must come from a managed secret store in
  production. Rotating it requires re-encrypting stored secrets; enrollment is
  disabled while the key is unset.

## Authorization (deny-by-default)

Roles are tenant-scoped through `memberships`: `owner`, `admin`, `provider`,
`coder`, `biller`, `auditor`, `read_only`. Endpoints explicitly list permitted
roles; unauthenticated requests get `401`, authorized-but-insufficient requests
get `403`. In Phase 1 only `owner`/`admin` may mutate organization data.

## Tenant isolation

Every tenant-scoped query filters by the `organization_id` carried in the access
token. Cross-tenant access returns `404` (never `403`) so resource existence is
not leaked. The repository base class (`TenantScopedRepository`) centralizes this
rule.

## Audit log

- **Append-only** in practice: the application has no update/delete path for
  `audit_events`; rows are only inserted.
- **Tamper-evident chain**: each event hashes the previous event's hash plus a
  canonical payload, keyed with a separate `AUDIT_HMAC_KEY`.
- **Limits (do not over-claim):**
  - Integrity means *the stored sequence has not been altered given the HMAC key*.
    It does **not** prove an event was truthful at write time.
  - A leaked `AUDIT_HMAC_KEY` breaks integrity.
  - The chain is global within one deployment (one database).
  - "Append-only" is enforced by the application, not by database triggers; a
    direct DB write could still tamper. Production hardening should add
    DB-level protections and external WORM/streaming of the chain.

## Session & CSRF

- The refresh token is delivered as an **HttpOnly**, **SameSite=Strict** cookie
  scoped to `/api/v1/auth`, with `Secure` enabled in production (`COOKIE_SECURE`).
- The refresh endpoint additionally validates the `Origin` header when present.
- SameSite=Strict is the primary CSRF defense; the Origin check is defense in
  depth. A same-site subdomain deployment should add an explicit CSRF token.

## Logging & errors

- A redacting filter/formatter scrubs sensitive keys (passwords, tokens, secrets,
  Authorization, clinical-note fields) from log records.
- Clinical text must never be logged; log metadata, not content.
- The global exception handler returns a normalized JSON error
  `{error: {code, message, request_id}}` and never includes stack traces, SQL, or
  request bodies.

## Rate limiting

- Sliding-window limiter keyed by client IP + path, with configurable limits
  (`RATE_LIMIT_AUTH`, `RATE_LIMIT_DEFAULT`).
- **Process-local** by default; correct only for a single-process deployment. A
  multi-worker deployment must back it with a shared store (Redis). The interface
  (`get_limiter`) is intentionally small for that swap.

## Secrets & key rotation

- All secrets come from environment variables or a managed secret store; none are
  committed (`*.env*` is gitignored except `.env.example`).
- Separate keys: `SECRET_KEY` (JWT), `AUDIT_HMAC_KEY` (audit), `MFA_ENCRYPTION_KEY`
  (MFA). Rotating `SECRET_KEY` invalidates access tokens; rotating the others has
  the documented effects above.

## Uploads & malware scanning (Phase 4)

Not yet implemented. When added: size/type allow-lists, validation, and a malware
scanning integration point before any file is stored or processed.

## AI data handling (Phase 2)

- Transmission is **disabled by default**. The coding workflow requires
  `ai_enabled`, and PHI-transmitting providers additionally require
  `ai_phi_approved`. The local mock provider transmits nothing and needs no gate.
- The DeepSeek adapter sends only documented parameters (model, messages,
  temperature, max_tokens, stream). It does **not** invent privacy/retention flags.
- The clinical note is treated as **untrusted data**: it is delimited in the prompt,
  and the system prompt states it must not override instructions or request secrets.
  No instruction embedded in a note is executed.
- Only **minimum necessary** data is sent (note + date of service + encounter
  context); no additional patient identifiers are forwarded.
- AI metadata (provider, model, prompt/schema versions, token counts, request id)
  is persisted in `coding_attempts`; **no chain-of-thought** is stored.
- Model credentials come only from `DEEPSEEK_API_KEY`; errors are sanitized — no
  key, request body, or response body appears in errors or logs.

## Known gaps to close before production

1. No email verification or account-recovery flow yet.
2. MFA enrollment/disable does not yet require a fresh re-authentication window
   beyond the access token.
3. No DB-level append-only enforcement or external audit-chain export.
4. Rate limiter is not shared across workers.
5. No backup/restore or retention/deletion workflow yet (planned).

## Frontend privacy (Phase 3)

- Clinical notes and evidence are never persisted to `localStorage`, `sessionStorage`,
  analytics, or caches; they are held only in component state for the current page.
- Clinical note text is never placed in query parameters or browser history.
- Note text and model output are rendered as plain text (React auto-escapes); they
  are never interpreted as HTML.
- No third-party analytics, tracking, or external content services are included.
- The frontend never calls DeepSeek or any provider directly; all coding goes
  through the backend's gated API.

## Background workers (Phase 4)

- Task arguments carry only the **job id**, never clinical note text, evidence, or
  tenant context — the worker re-fetches and verifies the job/encounter from the
  database (tenant-scoped) before processing.
- The database is authoritative for job state and results; Redis is broker-only and
  not a durable result store.
- AI and PHI approval gates are re-checked in the worker (same defaults disabled).
- Retries are bounded (exponential backoff) and exhausted to a stable `failed`
  state; no hidden chain-of-thought or raw provider responses are persisted.
- A broker failure marks the job `failed` and returns `503` — never a false success.
- Redis must not be exposed publicly; credentials come from environment configuration.
