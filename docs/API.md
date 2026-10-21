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
`GET /encounters` supports `limit` (1–200) and `offset`. Detail includes suggestions and review history.

### Submit for coding — `POST /api/v1/encounters/{id}/code`
Runs the coding workflow synchronously and returns a `CodingJobDetailOut`. Pass an
`Idempotency-Key` header to deduplicate retries. On a provider/output failure the
job is returned with `status: "failed"` and a sanitized `error_code`.

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
`invalid_code_type`.
