# Project Status

Last updated: Phase 3 completion.

| Phase | Scope | Status |
|---|---|---|
| 1 — Secure platform core | Tenant isolation, RBAC, Argon2 auth + refresh rotation/reuse detection, TOTP MFA, hash-chained audit, redacted logging, rate limiting, Alembic migrations, Next.js shell + login, Docker, docs, pytest | ✅ Complete |
| 2 — AI coding workflow | Provider-agnostic AI (DeepSeek + mock, disabled-by-default + PHI gate), coding-domain models + migration, structured coding workflow with exact-evidence validation, deterministic reference validation, coding API | ✅ Complete |
| **3 — Coding workspace UI** | Premium split-screen coding workspace, encounters dashboard (search/filter/pagination), create-encounter form, human-review workflow (approve/reject/correct), auth context + route guard, accessible component library, frontend tests | ✅ **Complete** |
| 4 — Documents & async jobs | Upload validation, object storage, malware-scan hook, PDF/CSV batch, Celery+Redis, transcription, CSV/XLSX export, PDF summary | Planned |
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

## Verification (Phase 3 + 3.1)

- ✅ Backend: 73 tests pass; `ruff check app tests` clean.
- ✅ Alembic cycle: `upgrade head` → `check` (no drift) → `downgrade -1` → re-`upgrade`.
- ✅ Frontend: `next lint` (no warnings/errors), `tsc --noEmit` clean, production build clean.
- ✅ Frontend tests: 17 pass (5 suites) via Jest + Testing Library.
- ✅ Phase 3.1 filtering: search/status/sort/order/pagination and cross-tenant tests pass.
- ⚠️ PostgreSQL migration verification not run (no PostgreSQL/Docker in this environment).

## Known limitations (Phase 3)

- The source note is returned only on the single-encounter detail (not in list
  responses) to minimize PHI exposure.
- No end-to-end browser (Playwright) tests yet (Phase 6); frontend coverage is
  component/unit level.
- Modifiers and payer-specific rules remain unimplemented (Phase 2+ backlog).
- PostgreSQL migration/integration not verified (no PostgreSQL/Docker available).
