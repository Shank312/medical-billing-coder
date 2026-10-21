# Data Model

Phase 1 schema (Alembic revision `71a37da41773`). All tenant-scoped rows are
reachable from `organizations`. Primary keys are UUID strings (36 chars) except
audit events. All timestamps are **naive UTC** stored in plain `DateTime` columns
for identical SQLite/PostgreSQL behavior.

## Conventions

- Table/constraint naming follows the SQLAlchemy naming convention in
  `app/db/base.py`.
- `created_at` / `updated_at` are set by the `TimestampMixin`.
- `ondelete="CASCADE"` is used for child rows owned by an org/user.

## Tables

### `organizations` (tenant)
| Column | Type | Notes |
|---|---|---|
| id | String(36) PK | UUID |
| name | String(255) | |
| slug | String(100) unique | URL-safe, unique |
| is_active | Boolean | |
| created_at / updated_at | DateTime | naive UTC |

### `users` (global identity)
| Column | Type | Notes |
|---|---|---|
| id | String(36) PK | UUID |
| email | String(320) unique | normalized lowercase |
| full_name | String(255) | |
| password_hash | String(255) | Argon2id |
| is_active | Boolean | |
| email_verified_at | DateTime nullable | reserved |
| created_at / updated_at | DateTime | |

A user is a global identity; access is granted per-organization via memberships.

### `memberships`
| Column | Type | Notes |
|---|---|---|
| id | String(36) PK | |
| user_id | FK users (CASCADE) | indexed |
| organization_id | FK organizations (CASCADE) | indexed |
| role | String(50) | owner/admin/provider/coder/biller/auditor/read_only |
| is_active | Boolean | |
| created_at / updated_at | DateTime | |

Unique on `(user_id, organization_id)`.

### `refresh_tokens`
| Column | Type | Notes |
|---|---|---|
| id | String(36) PK | |
| user_id | FK users (CASCADE) | indexed |
| organization_id | FK organizations (CASCADE) | indexed |
| token_hash | String(64) unique | SHA-256 of the opaque token |
| expires_at | DateTime | |
| revoked_at | DateTime nullable | |
| replaced_by_id | FK refresh_tokens (SET NULL) | rotation chain |
| ip_address / user_agent | String nullable | |

### `mfa_configs`
| Column | Type | Notes |
|---|---|---|
| id | String(36) PK | |
| user_id | FK users (CASCADE) unique | one config per user |
| secret_encrypted | String(512) | Fernet ciphertext |
| enabled | Boolean | |
| last_verified_at | DateTime nullable | |
| created_at / updated_at | DateTime | |

### `audit_events` (append-only)
| Column | Type | Notes |
|---|---|---|
| id | BigInteger (Postgres) / Integer (SQLite) autoincrement | chain order |
| organization_id | String(36) nullable | nullable for system events |
| actor_user_id | String(36) nullable | |
| action | String(120) | e.g. `auth.login` |
| resource_type / resource_id | String nullable | |
| ip_address / user_agent | String nullable | |
| metadata_json | Text nullable | redacted JSON |
| prev_hash | String(64) | previous event hash |
| event_hash | String(64) unique | HMAC over prev_hash + payload |
| occurred_at | String(40) ISO-8601 | part of the hashed payload |

Indexed on `organization_id`, `actor_user_id`, `action`, `occurred_at`.

### `audit_chain_state` (singleton)
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | always `1` |
| current_hash | String(64) | head of the chain |
| updated_at | String(40) | |

## Entity relationships

```
organizations 1──N memberships N──1 users
users         1──N refresh_tokens
users         1──1 mfa_configs
organizations 1──N refresh_tokens
```

## Indexes

- `ix_organizations_slug` (unique)
- `ix_users_email` (unique)
- `ix_memberships_user_id`, `ix_memberships_organization_id`
- `ix_refresh_tokens_user_id`, `_organization_id`, `_token_hash` (unique)
- `ix_mfa_configs_user_id` (unique)
- `ix_audit_events_*` on organization, actor, action, occurred_at

## Phase 2 tables (coding domain)

All tenant-scoped tables carry `organization_id` (or reach it via `encounters`).

### `encounters`
| Column | Type | Notes |
|---|---|---|
| id / organization_id / created_by | String FK | |
| date_of_service | Date | |
| encounter_type / place_of_service / payer_context | String nullable | billing context |
| patient_reference | String(255) nullable | opaque, minimal |
| status | String(30) | |

### `encounter_documents` (source note)
`encounter_id` FK, `document_type`, `content` (Text — the original note), `content_hash` (SHA-256). Stored separately from AI output.

### `coding_jobs`
`organization_id`, `encounter_id`, `client_request_id` (unique per org — idempotency), `status` (queued/running/completed/failed), `code_set_version`, `schema_version`, `prompt_version`, `error_code`, `completed_at`.

### `coding_attempts` (model metadata)
`job_id`, `provider_name`, `model_name`, `prompt_version`, `schema_version`, `code_set_version`, `request_id`, `status`, `latency_ms`, `prompt_tokens`/`completion_tokens`/`total_tokens`, `error_code`. No chain-of-thought.

### `coding_suggestions`
`encounter_id`, `job_id`, `code_type` (icd10cm/cpt/hcpcs/modifier), `code`, `description`, `confidence`, `rationale`, `applies_to`/`parent_suggestion_id` (modifiers), `validation_status`, `review_status`, `reviewed_by`/`reviewed_at`, `corrected_code`, `flags_json`.

### `evidence_spans`
`suggestion_id`, `quote` (verbatim), `start_offset`, `end_offset`.

### `review_decisions` (append-only history)
`suggestion_id`, `encounter_id`, `reviewer_id`, `decision`, `corrected_code`, `note`.

### `code_reference_sets` + `code_references` (global reference data)
Sets: `code_type`, `source`, `version` (unique together), effective dates, `record_count`, `imported_by`. References: `set_id`, `code` (unique per set), `description`, effective dates, `is_billable`, metadata.
