# API Reference (Phase 1)

Base URL: `http://localhost:8000` · Versioned prefix: `/api/v1`

Interactive OpenAPI docs are served at `/docs` in non-production environments.

## Conventions

- JSON bodies; the refresh endpoint also accepts the token via an HttpOnly cookie.
- Authenticated endpoints use `Authorization: Bearer <access_token>`.
- Errors are a single shape:

```json
{ "error": { "code": "unauthorized", "message": "Invalid email or password", "request_id": null } }
```

## Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health/live` | — | Liveness (no DB). |
| GET | `/health/ready` | — | Readiness (checks DB). Returns 503 when unavailable. |

## Auth

### Register — `POST /api/v1/auth/register`
Creates an organization, its owner, and signs in.

```json
{ "organization_name": "Acme Health", "full_name": "Jane Owner", "email": "jane@acme.test", "password": "a-strong-password-123!" }
```

Returns `201`:

```json
{
  "access_token": "…", "token_type": "bearer", "expires_in": 900, "refresh_token": "…",
  "user": { "id": "…", "email": "jane@acme.test", "full_name": "Jane Owner", "is_active": true, "created_at": "…" },
  "organization": { "id": "…", "name": "Acme Health", "slug": "acme-health", "is_active": true, "created_at": "…" }
}
```

Sets `refresh_token` as an HttpOnly cookie. Errors: `409 email_in_use` /
`slug_in_use`; `422` on invalid input.

### Login — `POST /api/v1/auth/login`

```json
{ "email": "jane@acme.test", "password": "a-strong-password-123!", "organization_id": null, "mfa_code": null }
```

Returns `200` with the same `AuthResponse` shape. `organization_id` is required
when the user belongs to multiple organizations (`400 organization_required`).
With MFA enabled, omitting `mfa_code` returns `401 mfa_required`.

### Refresh — `POST /api/v1/auth/refresh`
Rotates the refresh token. Token may be in the body or the cookie.

```json
{ "refresh_token": "…" }
```

Returns `200` with a new `AuthResponse`; reuse of a rotated token returns
`401 refresh_reuse` and revokes the session family.

### Logout — `POST /api/v1/auth/logout`
Revokes the presented refresh token (body or cookie). Idempotent. Clears the cookie.

### Revoke all sessions — `POST /api/v1/auth/sessions/revoke-all` (auth)
Revokes every active refresh token for the authenticated user+organization.

### Current user — `GET /api/v1/auth/me` (auth)
```json
{ "user": {…}, "organization": {…}, "roles": ["owner"] }
```

### MFA — `POST /api/v1/auth/mfa/{enroll,verify,disable}` (auth)
- `enroll` → `{ "secret": "JBSWY…", "otpauth_uri": "otpauth://totp/…" }` (secret shown once)
- `verify` (body `{ "code": "123456" }`) → `{ "message": "MFA enabled" }`
- `disable` (body `{ "password": "…", "code": "123456" }`) → `{ "message": "MFA disabled" }`

## Organizations (tenant-scoped, auth required)

All paths are relative to the authenticated user's organization; a path
`organization_id` that differs from the token's returns `404`.

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/organizations/{id}` | any | Read organization |
| PATCH | `/organizations/{id}` | owner, admin | Update name/slug |
| GET | `/organizations/{id}/users` | any | List members |
| POST | `/organizations/{id}/users` | owner, admin | Add member (`{email, full_name, role}`) |
| PATCH | `/organizations/{id}/users/{user_id}` | owner, admin | Update role/active |
| DELETE | `/organizations/{id}/users/{user_id}` | owner, admin | Remove member |

Member list/update/remove return `UserWithRole`:

```json
{ "user": { "id": "…", "email": "…", "full_name": "…", "is_active": true, "created_at": "…" }, "role": "coder" }
```

Guardrails: the last active owner cannot be demoted, deactivated, or removed
(`409 last_owner`).

## Coding endpoints (Phase 2)

All coding endpoints are tenant-scoped and role-gated. `ENCOUNTER_WRITE_ROLES`
(owner, admin, provider, coder) may create encounters and submit coding;
`REVIEW_ROLES` (owner, admin, coder, biller) may review; `REFERENCE_ADMIN_ROLES`
(owner, admin) may import code sets; any authenticated member may read.

### Create encounter — `POST /api/v1/encounters`
```json
{ "date_of_service": "2025-03-15", "note": "…clinical text…", "encounter_type": "office visit", "place_of_service": "11", "patient_reference": "…", "payer_context": "…" }
```
Returns `201` with the encounter. The note is stored separately from any AI output.

### List / get encounters — `GET /api/v1/encounters` and `GET /api/v1/encounters/{id}`
`GET /encounters` supports:
- `search` — case-insensitive match on `patient_reference` and `encounter_type` (never the note text).
- `status` — `all` (default), `coded`, `pending`, `not_coded`.
- `sort` — allowlisted: `date_of_service`, `created_at`, `patient_reference`, `encounter_type` (default `created_at`).
- `order` — `asc` | `desc` (default `desc`).
- `limit` (1–200, default 50) and `offset` (default 0); returns a reliable filtered `total`.

Invalid `sort`, `order`, or `status` return `400` with `invalid_sort`/`invalid_order`/
`invalid_status`. Detail includes the note, suggestions, and review history.

### Submit for coding — `POST /api/v1/encounters/{id}/code` → `202 Accepted`
Enqueues the coding job asynchronously and returns the persisted `CodingJobDetailOut`
with `status: "queued"`. Pass an `Idempotency-Key` header to deduplicate retries.
Poll `GET /coding-jobs/{id}` for completion. A broker/queue failure returns
`503 queue_unavailable` and marks the job `failed` — never a false success.

### List jobs — `GET /api/v1/coding-jobs`
Returns the authenticated organization's jobs (paginated via `limit`/`offset`), with
an optional `status` filter (`queued`/`running`/`completed`/`failed`).

### Get job — `GET /api/v1/coding-jobs/{id}`
Returns job status plus its suggestions (with evidence, validation status, review status).

### Review a suggestion — `POST /api/v1/encounters/{id}/suggestions/{sid}/review`
```json
{ "decision": "approved" | "rejected" | "corrected", "corrected_code": "…", "note": "…" }
```

### Code references — import / lookup / sets
- `POST /api/v1/code-references/import` (owner/admin)
- `GET /api/v1/code-references/lookup?code_type=&code=&date_of_service=`
  → `{ "code", "code_type", "status": "valid"|"date_invalid"|"unknown"|"reference_data_unavailable", "description", "version", "source" }`
- `GET /api/v1/code-references/sets`

## Error codes (non-exhaustive)

`unauthorized`, `forbidden`, `not_found`, `conflict`, `bad_request`,
`validation_error`, `rate_limited`, `internal_error`, `email_in_use`,
`slug_in_use`, `mfa_required`, `refresh_reuse`, `organization_required`,
`last_owner`, `already_member`, `invalid_role`, `ai_disabled`, `phi_not_approved`,
`provider_error`, `invalid_model_output`, `reference_data_unavailable`,
`note_required`, `corrected_code_required`, `invalid_decision`, `code_set_exists`,
`invalid_code_type`, `queue_unavailable`, `retry_exhausted`, `invalid_status`.

### Phase 3 additions

`GET /api/v1/encounters/{id}` now also returns the source note and workflow summary:
`note`, `coding_status` (latest job status), `review_status` (`pending`/`reviewed`),
and `missing_documentation` / `contradictions` (from the latest completed job).
`GET /api/v1/encounters` items include `coding_status` and `review_status` (but not
the note text). `CodingJobOut` includes `missing_documentation` and `contradictions`.

### Phase 5 additions — batch ingestion

- `POST /api/v1/batches` — create a batch (optional `date_of_service`).
- `POST /api/v1/batches/{id}/documents` — multipart upload of `.pdf`/`.csv` files
  (50 files max, 5 MB each, aggregate limits enforced).
- `GET /api/v1/batches` — list batches (paginated).
- `GET /api/v1/batches/{id}` — batch detail with per-document status.
- `POST /api/v1/batches/{id}/documents/{doc_id}/retry` — retry a failed document.

Document statuses: `pending`, `processing`, `completed`, `failed`, `requires_manual`.

#### CSV schema

Header: `date_of_service,note,encounter_type,place_of_service,patient_reference,payer_context`.
Required columns: `date_of_service` (YYYY-MM-DD) and `note`. The remaining columns
are optional. Row-level errors (`invalid_date`, `missing_note`, `note_too_long`,
`duplicate_row`) are recorded without silently dropping valid rows.

Batch error codes: `unsupported_type`, `file_too_large`, `empty_file`, `too_many_files`,
`not_in_batch`, `not_retryable`, `pdf_extraction_failed`, `encrypted_pdf`,
`pdf_too_many_pages`, `extracted_too_long`, `csv_schema_invalid`, `csv_no_valid_rows`,
`csv_too_many_rows`, `no_text`, `missing_date`.
