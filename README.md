# Medical Billing Coder

Secure, evidence-linked medical coding review for US medical practices, behavioral
health providers, billing teams, and multi-provider clinics.

**Phase 2 (current):** adds a provider-agnostic AI coding engine (DeepSeek + a
local mock behind one interface, disabled by default with a PHI approval gate),
tenant-scoped encounters/coding jobs/suggestions/evidence, a structured coding
workflow with exact-evidence validation and hallucination rejection, and
deterministic ICD-10/CPT/HCPCS reference validation — on top of the Phase 1 secure
core (tenant isolation, RBAC, refresh rotation + reuse detection, TOTP MFA,
hash-chained audit, redacted logging, rate limiting).

> **Compliance note:** this project is designed to *support* HIPAA-regulated
> workloads but is **not** certified HIPAA-compliant. No compliance claim is made
> by the presence of encryption or security controls. See
> [`docs/SECURITY.md`](docs/SECURITY.md) and
> [`docs/COMPLIANCE_CHECKLIST.md`](docs/COMPLIANCE_CHECKLIST.md).

---

## Architecture at a glance

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| Database | PostgreSQL 16 (production) / SQLite (local tests) |
| Migrations | Alembic |
| Background jobs | Celery + Redis (reserved for Phase 4) |
| AI | Provider-agnostic interface: DeepSeek + mock adapters, disabled by default with a PHI approval gate |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

## Repository layout

```
backend/   FastAPI app, SQLAlchemy models, Alembic migrations, pytest suite
frontend/  Next.js + TypeScript + Tailwind application
infra/     docker-compose.yml (PostgreSQL, Redis, backend, frontend)
docs/      Architecture, security, data model, API, compliance documentation
e2e/       Playwright tests (Phase 6)
```

## Prerequisites

- Python 3.12+
- Node.js 18.18+ (tested on 24.x) and npm
- Docker + Docker Compose (optional, for the full local stack)

---

## Backend — install, configure, run, test

Run these from a normal PowerShell terminal in `backend/`.

### 1. Install dependencies (standard venv)

```powershell
cd "D:\Medical Billing Coder\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

> **Alternative without a venv** (used to verify this repo in a restricted
> sandbox): install into a workspace folder and put it on `PYTHONPATH`:
>
> ```powershell
> python -m pip install -r requirements-dev.txt --target .\.deps --no-cache-dir
> $env:PYTHONPATH = "D:\Medical Billing Coder\backend\.deps;D:\Medical Billing Coder\backend"
> ```

### 2. Configure

```powershell
Copy-Item .env.example .env
# Edit .env: set SECRET_KEY, AUDIT_HMAC_KEY, and MFA_ENCRYPTION_KEY.
# Generate an MFA key with:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For a local SQLite run, set `DATABASE_URL=sqlite:///./mbc_dev.db` in `.env`.
For PostgreSQL, use `postgresql+psycopg2://user:pass@host:5432/mbc`.

### 3. Run migrations

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 4. Run the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Interactive docs: <http://127.0.0.1:8000/docs> · health: <http://127.0.0.1:8000/health/live>

### 5. Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

## Frontend — install, configure, run, build

```powershell
cd "D:\Medical Billing Coder\frontend"
npm install
Copy-Item .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                         # http://localhost:3000
```

Production build and checks:

```powershell
npm run lint
npm run typecheck
npm run build
```

---

## Docker (optional; not required for the SQLite test suite)

```powershell
cd "D:\Medical Billing Coder"
Copy-Item .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- Backend: <http://localhost:8000> (runs `alembic upgrade head` on start)
- Frontend: <http://localhost:3000>
- PostgreSQL: `localhost:5432` · Redis: `localhost:6379`

---

## API surface

- `POST /api/v1/auth/register` — create an organization + owner and sign in
- `POST /api/v1/auth/login` — email/password (+ optional `mfa_code`)
- `POST /api/v1/auth/refresh` — rotate refresh token (cookie or body)
- `POST /api/v1/auth/logout` — revoke the refresh token
- `POST /api/v1/auth/sessions/revoke-all` — revoke all sessions
- `POST /api/v1/auth/mfa/enroll` / `verify` / `disable` — TOTP MFA
- `GET  /api/v1/auth/me` — current user, organization, roles
- `GET/PATCH /api/v1/organizations/{id}` and member management under `/users`

**Phase 2 — coding:**
- `POST /api/v1/encounters` — create an encounter with a source note
- `GET /api/v1/encounters` and `GET /api/v1/encounters/{id}` — list / detail
- `POST /api/v1/encounters/{id}/code` — submit for coding (returns a job; supports `Idempotency-Key`)
- `POST /api/v1/encounters/{id}/suggestions/{sid}/review` — approve / reject / correct
- `GET /api/v1/coding-jobs/{id}` — job status + suggestions
- `POST /api/v1/code-references/import` — load an authorized code set (owner/admin)
- `GET /api/v1/code-references/lookup` and `/sets` — validate / list code sets

Full details in [`docs/API.md`](docs/API.md).

## Security summary

Tenant isolation at the repository layer, deny-by-default RBAC, Argon2id password
hashing, hashed rotating refresh tokens with reuse detection, Fernet-encrypted
MFA secrets, an HMAC-chained append-only audit log, redacted logging, rate
limiting, and a normalized error contract that never leaks internals. See
[`docs/SECURITY.md`](docs/SECURITY.md) for boundaries and known limits.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/SECURITY.md`](docs/SECURITY.md)
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)
- [`docs/API.md`](docs/API.md)
- [`docs/COMPLIANCE_CHECKLIST.md`](docs/COMPLIANCE_CHECKLIST.md)
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
