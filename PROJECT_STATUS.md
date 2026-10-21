# Project Status

Last updated: Phase 7 completion.

| Phase | Scope | Status |
|---|---|---|
| 1 — Secure platform core | Tenant isolation, RBAC, Argon2 auth + refresh rotation/reuse detection, TOTP MFA, hash-chained audit, redacted logging, rate limiting, Alembic migrations, Next.js shell + login, Docker, docs, pytest | ✅ Complete |
| 2 — AI coding workflow | Provider-agnostic AI (DeepSeek + mock, disabled-by-default + PHI gate), coding-domain models + migration, structured coding workflow with exact-evidence validation, deterministic reference validation, coding API | ✅ Complete |
| 3 — Coding workspace UI | Premium split-screen coding workspace, encounters dashboard (search/filter/pagination), create-encounter form, human-review workflow, auth context + route guard, accessible component library, frontend tests | ✅ Complete |
| 4 — Async coding jobs | Celery + Redis worker, durable queued→running→completed/failed lifecycle, idempotent at-least-once delivery, bounded retries, stale-job recovery, 202 async API + frontend polling | ✅ Complete |
| 5 — Batch document ingestion | Batch/document models + migration, secure multi-file upload, PDF text extraction, strict CSV import, staged idempotent worker pipeline, batch status API + frontend | ✅ Complete |
| 6 — Exports & coding summaries | CSV/XLSX collection exports, per-encounter PDF summary, batch CSV export, formula-injection + filename safeguards, audit, frontend actions | ✅ Complete |
| **7 — Hardening & verification** | Fail-closed production config validation, security headers, storage/export/cross-tenant hardening tests, PostgreSQL/Redis integration scaffolding, operations/retention documentation | ✅ **Complete** |
| 7b — Documents (remaining) | Audio transcription, malware-scan hook, object storage | Planned |
| 8 — SaaS & durable memory | Subscriptions, usage ledger, Stripe + webhooks, tenant-scoped memory (pgvector optional) | Planned |
| 9 — Interop | FHIR export, dashboards, usage metrics, browser E2E (Playwright) | Planned |

## Phase 3 — delivered

- **Workspace** — split-screen: clinical note on the left (with exact evidence
  highlighting + scroll-to-source), candidate suggestions grouped by diagnoses /
  procedures / modifiers on the right, plus missing-documentation and contradiction
  warnings and a review-history section.
- **Screens** — encounters dashboard (search, status filter, pagination, loading /
  empty / error states), create-encounter form (client validation + char limits +
  duplicate-submission prevention), encounter workspace with review workflow.
- **Review workflow** — approve / reject / correct with inline confirmation and a
  required corrected code; decisions reflect only after the server confirms.
- **Auth** — in-memory token context, silent refresh on load, 401 handling, route
  guard, accessible app shell (sidebar + topbar).
- **Honest uncertainty** — reference-data-unavailable is shown explicitly; model
  confidence is labeled uncalibrated; codes are never shown as validated unless
  deterministic validation succeeded.
- **Backend (smallest compatible addition)** — encounter detail now returns the
  source `note`, `coding_status`/`review_status`, and `missing_documentation` /
  `contradictions`; coding jobs persist missing-docs/contradictions. Migration
  `c3ea3c0c5da2_phase_3_note_and_status_exposure`.

### Phase 3.1 — hardening

- **Server-side encounter filtering** — `GET /api/v1/encounters` now accepts
  `search` (case-insensitive match on `patient_reference`/`encounter_type` only —
  never the note text), `status` (`all`/`coded`/`pending`/`not_coded`), allowlisted
  `sort` (`date_of_service`/`created_at`/`patient_reference`/`encounter_type`) and
  `order` (`asc`/`desc`), plus validated `limit`/`offset` with a reliable filtered
  total. Filtering, counting, sorting, and pagination all run in the database under
  tenant scoping. No schema change was required.

## Phase 4 — delivered (async coding jobs)

- **Celery + Redis** — `app/celery_app.py` (broker-only; DB stays authoritative) and
  `app/tasks/coding.py` (`coding.process_job`, acks-late, bounded exponential-backoff
  retries). Task args carry only the job id — never the note or tenant context.
- **Lifecycle** — `queued → running → completed|failed` with an atomic
  `queued → running` claim (idempotent under duplicate delivery) and a
  `recover_stale_jobs` sweep for stale `running` and orphaned `queued` jobs.
- **Safe enqueue** — the job is committed before publication; a broker failure marks
  it `failed` and returns `503` (no false success). Idempotency key dedupes retries.
- **API** — submit returns `202` + queued job; `GET /coding-jobs/{id}` and new
  `GET /coding-jobs` (paginated, status-filtered) are tenant-scoped.
- **Frontend** — the workspace polls `GET /coding-jobs/{id}` with bounded frequency
  and stops on terminal state; shows queued/running and sanitized failure states.
- **Migration** — `9b95153a9335_phase_4_async_job_fields` (`started_at`,
  `attempt_number`). Docker Compose gains a `worker` service.

## Phase 5 — delivered (batch document ingestion)

- **Models** — `ingestion_batches` + `ingestion_documents` (migration
  `bafb83f983e4`): storage reference, content hash, per-document status/error,
  extracted text, encounter/coding-job links, CSV row results.
- **Storage** — `app/storage.py` abstraction with a non-public local-filesystem dev
  implementation (explicitly not production-durable); internally generated,
  sanitized keys; streamed writes.
- **Upload API** — `POST /batches`, `POST /batches/{id}/documents` (multi-file,
  type/extension/signature checks, size limits), list/detail/retry endpoints.
- **PDF extraction** — `pypdf` text extraction with page/text limits; encrypted/
  malformed PDFs fail; image-only PDFs → `requires_manual` (no OCR).
- **CSV import** — strict schema (`date_of_service`, `note` + optional encounter
  columns) with row-level errors and duplicate detection; no silent row drops.
- **Worker pipeline** — `ingestion.process_document` reuses Phase 4 Celery:
  claim → extract/parse → create encounters → enqueue coding → refresh batch,
  idempotent and bounded-retry.
- **Frontend** — `/batches` (list/create/upload) and `/batches/[id]` (status table,
  polling, retry, navigate to encounter workspace).

## Phase 6 — delivered (exports & coding summaries)

- **CSV export** — `GET /encounters/export.csv` (collection, uses the validated
  `search`/`status`/`sort`/`order` filters) and `GET /batches/{id}/export.csv`
  (batch/document status). Deterministic schemas with formula-injection
  neutralization and correct UTF-8/quoting.
- **XLSX export** — `GET /encounters/export.xlsx` (openpyxl) with `Encounters`,
  `Coding Results`, `Review History`, and `Warnings` worksheets; frozen header rows,
  text-only cells, no formulas/macros.
- **PDF summary** — `GET /encounters/{id}/summary.pdf` (reportlab): encounter ref,
  coding/review status, suggestions with review decisions, warnings, an explicit
  UNREVIEWED banner, and a disclaimer (not a claim/guarantee/certification).
- **Review semantics** — AI-suggested vs approved/rejected/corrected are distinct;
  a code is labeled approved only from a persisted human decision.
- **Safety** — bounded rows (`max_export_rows`), sanitized cells, UUID/fixed
  filenames, XML-escaped PDF text, synchronous response (no persisted artifacts).
- **Audit** — `export.generated` events (actor, org, resource, format, row count)
  with no clinical content.
- **Frontend** — export actions on the encounters dashboard (CSV/XLSX), the coding
  workspace (PDF summary), and the batch detail page (CSV).

## Phase 7 — delivered (hardening & verification)

- **Production config validation** — fail-closed on dev-placeholder secrets, a
  missing MFA key, `COOKIE_SECURE=false`, or a wildcard CORS origin in `production`.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Cache-Control: no-store` on API responses; HSTS in production.
- **Hardening tests** — production-config rejection, header presence, health
  endpoints, storage path-traversal, formula-injection control characters,
  export-no-AI-invocation, and cross-tenant review (12 new tests).
- **Integration scaffolding** — `tests/test_integration_infra.py` skips honestly
  without `TEST_POSTGRES_URL`/`TEST_REDIS_URL`; documented migration/worker/E2E
  procedures in `docs/OPERATIONS.md`.
- **Operations docs** — retention, backup, offboarding, monitoring, and incident
  response posture; `docs/SECURITY.md` records remaining gaps (recovery, email
  verification, MFA reauth, distributed rate limiting, DB-level audit enforcement).

## Verification (Phase 7)

- ✅ Backend: 120 tests pass + 3 integration tests skipped (no PostgreSQL/Redis);
  `ruff check app tests` clean.
- ✅ Alembic `check` — no drift (no migration added).
- ✅ Frontend: `next lint` (no warnings/errors), `tsc --noEmit` clean, production build clean (8 routes).
- ✅ Frontend tests: 17 pass (5 suites) via Jest + Testing Library.
- ⚠️ PostgreSQL, Redis/Celery, and browser E2E verification NOT run (unavailable here).

## Known limitations (Phase 7)

- PostgreSQL/Redis integration and browser E2E are written as skippable scaffolding
  and documented manual procedures, but were not executed in this environment.
- No account recovery/email verification, no MFA step-up, in-memory rate limiting,
  and application-level (not database-enforced) audit.
- Local filesystem storage is development-only; no object storage, malware scan,
  OCR, backups (untested), or automatic retention/deletion.
- Cancellation remains deferred; async delivery is at-least-once (idempotent effects).
