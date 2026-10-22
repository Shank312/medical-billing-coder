# Operations & Retention

This document records the current operational posture of Medical Billing Coder as
of Phase 7. It states what is implemented, what is assumed, and what remains to be
built. Nothing here constitutes a compliance or HIPAA certification claim.

## Retention (current state)

| Data | Retention | Notes |
|---|---|---|
| Original uploads (files) | Until explicitly deleted (no automatic expiry) | Local filesystem storage is development-only; object storage is not implemented |
| Extracted text / source notes | Until explicitly deleted | Stored in `encounter_documents.content` and `ingestion_documents.extracted_text` |
| Coding suggestions + review history | Append-only; no automatic expiry | Review decisions are never overwritten |
| Audit log | Append-only, hash-chained; no automatic expiry | `audit_events` + hash chain anchor |
| Exported files | Not persisted (synchronous response only) | The client is responsible for secure storage after download |

No automatic deletion policy is implemented. Do **not** add automatic deletion of
clinical records or audit history without an explicit, reviewed retention policy.

## Backup and restore

- **Backups are not operational.** No backup jobs, snapshotting, or restore testing
  has been performed. A production deployment must add database backups (and object
  storage backup/versioning once object storage exists) and must actually test
  restore before claiming backups work.
- The audit hash chain must be included in backups (it spans `audit_events` and the
  `audit_chain` anchor table).

## Deletion and tenant offboarding

- Foreign keys use `ondelete="CASCADE"` for org/user-owned rows, so deleting an
  organization cascades to its encounters, jobs, suggestions, batches, and
  documents — but this is **not** an implemented offboarding flow and has **not**
  been exercised as such. Build and test an explicit offboarding procedure (including
  audit retention and a mandatory review step) before relying on cascade deletes.

## Monitoring and alerting

- `/health/live` (liveness) and `/health/ready` (database connectivity) are available.
- No metrics, alerting, or centralized logging exists. A production deployment must
  add structured-log shipping, worker-queue depth monitoring, and failure alerting.

## Security incident response

- No incident-runbook exists. Production readiness requires: credential rotation
  procedures, audit-log export for forensics, secret-revocation steps, and a
  documented contact/escalation path. The append-only, hash-chained audit log is the
  intended forensic source.

## Integration-test procedure (requires real infrastructure)

The offline suite never substitutes for these. Run them only against a dedicated,
disposable test environment. The simplest path is the Phase 8 test stack:

```powershell
cd "D:\Medical Billing Coder"
.\scripts\test-infra.ps1 up            # postgres(5433) + redis(6380) + api(8001) + worker + frontend(3001)
.\scripts\test-infra.ps1 integration   # real PostgreSQL + Redis/Celery tests
.\scripts\test-infra.ps1 e2e           # Playwright browser tests
.\scripts\test-infra.ps1 logs          # inspect service logs (no secrets are logged)
.\scripts\test-infra.ps1 clean         # tear down and drop test data
```

The test stack uses a disposable PostgreSQL tmpfs volume, a non-persistent Redis
(`--save ""`), synthetic test credentials (`mbc_test` / `mbc_test_password`), and the
local mock AI provider — no external AI or PHI transmission.

Run the pieces directly (from `backend/`):

```powershell
$env:TEST_POSTGRES_URL = "postgresql+psycopg2://mbc_test:mbc_test_password@localhost:5433/mbc_test"
$env:TEST_REDIS_URL   = "redis://localhost:6380/0"
python -m pytest integration_tests -v
```

Full migrations against PostgreSQL (destructive only on `*_test*` databases):

```powershell
$env:DATABASE_URL = $env:TEST_POSTGRES_URL
python -m alembic upgrade head
python -m alembic check           # no drift
python -m alembic downgrade -1    # then re-upgrade (isolated test DB only)
```

Real Redis/worker verification (the `integration_tests/test_redis_celery.py` tests
require the `worker-test` service from the compose stack to be running):

```powershell
python -m celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=2
```

Browser E2E (requires Playwright + browsers):

```powershell
cd "D:\Medical Billing Coder\e2e"
npm install && npx playwright install chromium
E2E_BASE_URL=http://localhost:3001 E2E_API_URL=http://localhost:8001 npx playwright test
```

CI (` .github/workflows/ci.yml`) separates unit, integration (real Postgres + Redis +
a live worker), and browser E2E jobs; unit tests never require Docker.

## Operational safety

- The test database is a separate `mbc_test` database on a tmpfs volume; the test
  compose stack never mounts a production database, and the migration commands are
  guarded to `*_test*` databases.
- Service logs are plaintext and contain no secrets or clinical notes; inspect them
  with `docker compose -f infra/docker-compose.test.yml logs`.
- Failed jobs are diagnosed via `GET /coding-jobs/{id}` (sanitized `error_code`) and
  the audit log; retry is explicit (batch documents only), never automatic for
  coding.
- Test resources are removed with `.\scripts\test-infra.ps1 clean` (`down -v`).

Before a production deployment, the mandatory checks are: full unit suite, real
PostgreSQL integration suite, real Redis/Celery integration suite, browser E2E,
`alembic check` (no drift), and a secret scan. Passing these does **not** imply HIPAA
compliance or production readiness.
