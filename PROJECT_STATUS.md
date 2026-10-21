# Project Status

Last updated: Phase 4 completion.

| Phase | Scope | Status |
|---|---|---|
| 1 — Secure platform core | Tenant isolation, RBAC, Argon2 auth + refresh rotation/reuse detection, TOTP MFA, hash-chained audit, redacted logging, rate limiting, Alembic migrations, Next.js shell + login, Docker, docs, pytest | ✅ Complete |
| 2 — AI coding workflow | Provider-agnostic AI (DeepSeek + mock, disabled-by-default + PHI gate), coding-domain models + migration, structured coding workflow with exact-evidence validation, deterministic reference validation, coding API | ✅ Complete |
| 3 — Coding workspace UI | Premium split-screen coding workspace, encounters dashboard (search/filter/pagination), create-encounter form, human-review workflow, auth context + route guard, accessible component library, frontend tests | ✅ Complete |
| **4 — Async coding jobs** | Celery + Redis worker, durable queued→running→completed/failed lifecycle, idempotent at-least-once delivery, bounded retries, stale-job recovery, 202 async API + frontend polling | ✅ **Complete** |
| 4b — Documents & batch processing | Upload validation, object storage, malware-scan hook, PDF/CSV batch, transcription, CSV/XLSX export, PDF summary | Planned |
| 5 — SaaS & durable memory | Subscriptions, usage ledger, Stripe + webhooks, tenant-scoped memory (pgvector optional) | Planned |
| 6 — Interop & hardening | FHIR export, dashboards, usage metrics, Playwright e2e, security hardening | Planned |

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

## Verification (Phase 4)

- ✅ Backend: 86 tests pass; `ruff check app tests` clean.
- ✅ Alembic cycle: `upgrade head` → `check` (no drift) → `downgrade -1` → re-`upgrade`.
- ✅ Frontend: `next lint` (no warnings/errors), `tsc --noEmit` clean, production build clean.
- ✅ Frontend tests: 17 pass (5 suites) via Jest + Testing Library.
- ✅ Offline async tests use eager Celery + direct task/service calls (no Redis required).
- ⚠️ Real Redis broker and PostgreSQL not verified (no Redis/Docker/PostgreSQL here).

## Known limitations (Phase 4)

- Real Redis/PostgreSQL integration not verified in this environment (eager Celery
  and SQLite are used for offline tests; real-broker behavior is documented, not run).
- Cancellation is not implemented (deferred); jobs reach `completed`/`failed` only.
- Delivery is at-least-once with idempotent effects — not exactly-once (documented).
- Document/batch processing, transcription, and exports remain deferred (Phase 4b).
- No end-to-end browser (Playwright) tests yet (Phase 6).
- PostgreSQL migration/integration not verified (no PostgreSQL/Docker available).
