# Pilot Readiness & Deployment Checklist

This document is the release-readiness checklist for a **restricted, synthetic-data
demo or controlled pilot**. It is not a production-readiness or compliance claim.

## Readiness checklist

| # | Capability | Status | Evidence | Risk / next action |
|---|---|---|---|---|
| 1 | Auth (Argon2, refresh rotation, reuse detection, MFA) | ✅ Done | Phase 1 + tests | MFA recovery/step-up remains open |
| 2 | RBAC + tenant isolation | ✅ Done | Phase 1; cross-tenant tests | Enforced at repository layer |
| 3 | Audit (append-only, hash-chained) | ✅ Done | Phase 1 | App-level, not DB-enforced |
| 4 | Redacted logging + normalized errors | ✅ Done | Phase 1 + 7 | Verify in staging |
| 5 | AI coding (mock + DeepSeek, gated) | ✅ Done | Phase 2 | PHI gate default-off |
| 6 | Coding workspace + human review | ✅ Done | Phases 2–3 | Preserve review semantics |
| 7 | Async jobs (Celery/Redis, idempotent) | ✅ Done | Phase 4 | Real Redis not verified here |
| 8 | Batch ingestion (PDF/CSV, storage) | ✅ Done | Phase 5 | Local storage is dev-only |
| 9 | Exports (CSV/XLSX/PDF) | ✅ Done | Phase 6 | Bounded, sanitized |
| 10 | Security hardening + config validation | ✅ Done | Phase 7 | Recovery/email-verify open |
| 11 | Integration/E2E test stack + CI | ✅ Authored | Phase 8 | **Not executed here — no Docker** |
| 12 | Reference-data import + validation | ✅ Done | Phase 2 | Licensed CPT data required |
| 13 | Malware scanning | ❌ Open | — | Integration point isolated |
| 14 | Object storage (uploads) | ❌ Open | — | Local FS is dev-only |
| 15 | Backup / restore (tested) | ❌ Open | — | Not operational |
| 16 | Monitoring / alerting | ❌ Open | — | Health checks only |

## Blockers ranked by severity

1. **Real PostgreSQL/Redis/E2E not verified** — the suites exist but were not run here
   (Docker unavailable). Run `scripts/test-infra.ps1` on a Docker-capable host before
   any pilot.
2. **Local upload storage is not durable** — swap `STORAGE_DIR` for object storage
   before a multi-user pilot; the storage abstraction is ready for that swap.
3. **No malware scanning** — uploads must not be described as scanned.
4. **No tested backups/restore** — backups are not operational.
5. **Auth gaps** — no account recovery, email verification, or MFA step-up.
6. **AI/PHI transmission** — remains default-disabled; enable only with a BAA and
   explicit approval, never for the demo with real data.

## Restricted synthetic-data demo — deployment checklist

Use **synthetic data only**. Never demo with real patient data.

- [ ] HTTPS terminated in front (reverse proxy); `COOKIE_SECURE=true`.
- [ ] `APP_ENV=production` (validator fails closed on dev placeholders, missing MFA
      key, `COOKIE_SECURE=false`, or wildcard CORS).
- [ ] Separate `development`, `test`, and `production` environments and databases;
      never point tests at the demo database.
- [ ] Managed PostgreSQL with private networking; non-public Redis (no public port).
- [ ] Real `SECRET_KEY`, `AUDIT_HMAC_KEY`, and `MFA_ENCRYPTION_KEY` from a secrets
      store — never the `.env.example` placeholders, never committed.
- [ ] Object storage for uploads with private access controls (not local FS).
- [ ] Database backups enabled and **restore tested** before demo day.
- [ ] `/health/live` + `/health/ready` wired into the reverse proxy.
- [ ] Logs shipped to a collector; verify no secrets or clinical text in logs.
- [ ] Rollback plan: tagged image, one-command migration downgrade (tested on a copy),
      documented DB snapshot restore.
- [ ] Rate limiting enabled and proxy configured for the expected client IP scheme.
- [ ] Do not expose development ports (5432/6379/8000/3000) publicly; bind to
      localhost or a private network only.
- [ ] Access restricted to authorized demo users with least-privilege roles.
- [ ] `AI_ENABLED=false` for the demo unless you explicitly run the local mock
      provider — never transmit synthetic notes to an external AI provider.

## Decision

**Controlled-pilot-ready for synthetic data only**, pending execution of the real
PostgreSQL/Redis/browser E2E suites on Docker-capable infrastructure and the storage
swap described above. **Not production-ready** and **not** HIPAA-compliant; see
`COMPLIANCE_CHECKLIST.md`.
