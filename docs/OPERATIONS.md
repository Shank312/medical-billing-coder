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
disposable test environment.

```powershell
cd "D:\Medical Billing Coder\backend"
$env:TEST_POSTGRES_URL = "postgresql+psycopg2://mbc:change_me@localhost:5432/mbc_test"
$env:TEST_REDIS_URL   = "redis://localhost:6379/0"
python -m pytest tests/test_integration_infra.py -v   # basic connectivity + rollback
```

Full migrations against PostgreSQL (destructive only on `*_test*` databases):

```powershell
$env:DATABASE_URL = $env:TEST_POSTGRES_URL
python -m alembic upgrade head
python -m alembic check           # no drift
python -m alembic downgrade -1    # then re-upgrade (isolated test DB only)
```

Real Redis/worker verification (manual, in `backend/`):

```powershell
python -m celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=2
# Submit coding via the API, terminate the worker mid-task, restart it, and confirm
# stale 'running' jobs are recovered by recover_stale_jobs and never double-process.
```

Browser E2E (requires Playwright + browsers, not installed here):

```powershell
cd "D:\Medical Billing Coder\e2e"
npm install && npx playwright install
npx playwright test
```
