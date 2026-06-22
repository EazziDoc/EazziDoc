# EazziDoc

AI-powered medical imaging diagnostics platform built for underserved communities across Africa. Patients upload medical images (X-ray, MRI, fundus, skin, mammography), receive a structured AI diagnostic report within minutes, and book a consultation with a verified doctor — all from a single interface.

> **Status:** Active development. Core product shipped. Admin dashboard, doctor credentialing, and account management live. See [ROADMAP](docs/ROADMAP.md).

---

## What's been built

| Area | Status | Notes |
|---|---|---|
| Patient portal | ✅ | Upload, diagnoses, appointments, settings, account deletion |
| Doctor portal | ✅ | Review queue, appointments, credential upload, pending approval page |
| Admin portal | ✅ | Separate login, dashboard, user management, doctor approval, audit logs |
| AI pipeline | ✅ | Gemini Vision primary, Groq fallback, async via Celery |
| Payments | ✅ | Stripe Checkout, webhook-driven status, per-appointment fee |
| Doctor registration approval | ✅ | Qualifications catalogue, cert upload, admin approve/reject workflow |
| Admin registration | ✅ | Invite-code gated; no public path to create admin accounts |
| Dark mode | ✅ | System/manual toggle across all portals (patient, doctor, admin) |
| Account moderation | ✅ | Admin ban/unban/delete; self-service patient and doctor account deletion |
| Email notifications | ✅ | Welcome, diagnosis ready, settings changed |
| Monitoring | ✅ | Sentry, Prometheus, Grafana dashboard |

---

## Architecture

```
Browser (Next.js 14)
    │
    ├── /                   Patient portal
    ├── /doctor/*           Doctor portal
    └── /admin/*            Admin portal (separate login, dark theme)
         │
         ▼
FastAPI (Uvicorn)           REST API, JWT auth, rate limiting
    │
    ├── PostgreSQL           Primary store (SQLAlchemy 2.0 async + asyncpg)
    ├── Redis                Celery broker + result backend
    ├── Celery Worker        AI pipeline tasks (image analysis)
    └── Cloudflare R2        Medical image + certification document storage

AI Pipeline (Celery task):
    Gemini 2.0 Flash Vision  → structured report
    Groq Llama 3.3 70b       ← fallback for unknown modalities or Gemini failure
```

The API and worker share the same Docker image. The frontend is a separate Next.js app deployed independently on Vercel. All application data flows through the REST API — the frontend is a pure client-side SPA.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI 0.115 | Async throughout, Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) | asyncpg driver |
| Migrations | Alembic | Sequential revision IDs |
| Task queue | Celery 5.4 + Redis 7 | AI pipeline, email dispatch |
| Auth | JWT (HS256, 15 min) + opaque refresh tokens (7 days, httpOnly cookie) | Tokens never touch localStorage |
| Storage | Cloudflare R2 via boto3 S3 API | Presigned URLs, no public bucket |
| AI — primary | Google Gemini 2.0 Flash Vision | Modality detection + structured report |
| AI — fallback | Groq Llama 3.3 70b | Kicks in when Gemini fails or modality unknown |
| Payments | Stripe Checkout Sessions | Patient-side checkout, webhook-driven status |
| Frontend | Next.js 14 App Router + TypeScript | TanStack Query, Tailwind CSS |
| Dark mode | `next-themes` + Tailwind `darkMode: "class"` | System preference + manual toggle |
| Monitoring | Sentry (errors) + Prometheus + Grafana | Structured JSON logs in production |
| Deployment | Fly.io (API + worker) · Vercel (frontend) | Johannesburg region primary |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose v2 (`docker compose`, not `docker-compose`)
- Node.js 18+ and npm (for frontend)
- Python 3.11+ (optional — only needed to run backend tests outside Docker)

### 1. Clone and configure

```bash
git clone git@github.com:EazziDoc/EazziDoc.git
cd EazziDoc
```

Copy the environment template and fill in values:

```bash
cp backend/.env.example backend/.env
```

Minimum required values to run locally:

```env
DATABASE_URL=postgresql+asyncpg://eazzidoc:eazzidoc@db:5432/eazzidoc
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ADMIN_INVITE_CODE=any-secret-phrase     # required to use /admin/register
SMTP_HOST=                              # leave blank to skip emails in dev
GOOGLE_API_KEY=                         # Gemini — required for AI pipeline
GROQ_API_KEY=                           # Groq fallback — required for AI pipeline
CLOUDFLARE_R2_ACCOUNT_ID=
CLOUDFLARE_R2_ACCESS_KEY_ID=
CLOUDFLARE_R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_BUCKET_NAME=
STRIPE_SECRET_KEY=                      # Stripe test key — required for payments
```

### 2. Start the backend

```bash
docker compose up --build
```

This starts Postgres, Redis, the API server, and the Celery worker. Alembic migrations run automatically on startup.

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The `backend/app/` directory is volume-mounted into the container. Uvicorn runs with `--reload`, so code changes take effect immediately without rebuilding. Only rebuild (`--build`) when dependencies or the Dockerfile itself change.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000.

---

## User Portals

### Patient portal — `/`

Register at `/register`, log in at `/login`. Patients can:
- Upload medical images and receive AI diagnostic reports
- View past diagnoses and doctor-written notes
- Book and manage appointments with verified doctors
- Pay for consultations via Stripe Checkout
- Delete their account from the Settings page (diagnosis history is retained)

### Doctor portal — `/doctor`

Register at `/register` (select Doctor role). Doctors submit qualifications and upload certifications during registration. The account stays in **pending review** until an admin approves it. Once approved:
- Review the AI diagnosis queue and add clinical notes
- Manage appointments (confirm, complete, cancel)
- Upload additional certification documents at any time
- Delete their account from the Settings page

### Admin portal — `/admin`

Separate login at `/admin/login`. Admin accounts can only be created via `/admin/register` with a valid invite code (set via `ADMIN_INVITE_CODE` env var — if unset, registration is disabled).

Admins can:
- View platform-wide stats, diagnosis queue, and audit logs
- Manage all users: view, ban/unban, or permanently delete patients and doctors
- Review doctor registration applications: approve or reject with a written reason; download submitted certifications; export as PDF
- Re-queue stuck diagnoses

---

## Project Structure

```
EazziDoc/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Route handlers
│   │   │   ├── auth.py      #   Register, login, refresh, logout, admin register
│   │   │   ├── patients.py  #   Patient/doctor profiles, cert upload, account deletion
│   │   │   ├── appointments.py
│   │   │   ├── diagnoses.py
│   │   │   ├── admin.py     #   Admin dashboard, user moderation, doctor approval
│   │   │   └── payments.py
│   │   ├── core/            # Config, DB session, JWT, dependencies,
│   │   │                    #   rate limiter, Celery app, metrics
│   │   ├── models/          # SQLAlchemy ORM models (User, Patient, Doctor,
│   │   │                    #   Diagnosis, Appointment, RefreshToken, AuditLog)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # AI pipeline, email, storage, payments
│   │   └── tests/           # pytest integration test suite
│   ├── alembic/             # Database migrations (0001 → 0003)
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── app/
│   │   ├── (admin-portal)/  # /admin/login, /admin/register (dark theme, standalone layout)
│   │   ├── (auth)/          # /login, /register (multi-step for doctors)
│   │   └── (dashboard)/     # Shared sidebar layout
│   │       ├── patient/     #   Dashboard, upload, diagnoses, appointments, settings
│   │       ├── doctor/      #   Dashboard, queue, appointments, patients, settings, pending
│   │       └── admin/       #   Overview, users, doctors, diagnoses, queue, audit-logs
│   ├── components/
│   │   ├── nav/sidebar.tsx  # Role-aware sidebar with dark mode toggle
│   │   └── ui/              # Button, Card, Input, Badge, ConfirmDialog, ThemeToggle
│   └── lib/                 # API client (api.ts), auth context, types, utils
│
├── docs/
│   └── ROADMAP.md
├── docker-compose.yml
├── docker-compose.monitoring.yml   # Prometheus + Grafana
└── SECURITY.md
```

---

## Environment Variables

| Group | Variable | Required | Notes |
|---|---|---|---|
| Database | `DATABASE_URL` | ✅ | asyncpg connection string |
| Auth | `SECRET_KEY` | ✅ | JWT signing key |
| Auth | `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Default 15 |
| Auth | `REFRESH_TOKEN_EXPIRE_DAYS` | — | Default 7 |
| Auth | `ADMIN_INVITE_CODE` | ✅ (for admin reg.) | Leave empty to disable `/admin/register` |
| Storage | `CLOUDFLARE_R2_ACCOUNT_ID` | ✅ | |
| Storage | `CLOUDFLARE_R2_ACCESS_KEY_ID` | ✅ | |
| Storage | `CLOUDFLARE_R2_SECRET_ACCESS_KEY` | ✅ | |
| Storage | `CLOUDFLARE_R2_BUCKET_NAME` | ✅ | |
| Storage | `CLOUDFLARE_R2_PUBLIC_URL` | — | Public CDN URL if bucket is public |
| AI | `GOOGLE_API_KEY` | ✅ | Gemini Vision |
| AI | `GROQ_API_KEY` | ✅ | Groq fallback |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | — | Leave blank to skip in dev |
| Payments | `STRIPE_SECRET_KEY` | ✅ | |
| Payments | `STRIPE_WEBHOOK_SECRET` | ✅ | For webhook signature verification |
| Payments | `CONSULTATION_FEE_CENTS` | — | Default 5000 ($50.00) |
| Monitoring | `SENTRY_DSN` | — | Omit to disable |
| CORS | `BACKEND_CORS_ORIGINS` | — | JSON list, default `["http://localhost:3000"]` |

---

## Running Tests

Tests are integration tests that run against a real database. Mocking the DB is explicitly avoided — the test suite exists to catch real query and migration failures.

```bash
# Inside the backend container
docker compose exec backend pytest

# Or locally with a venv
cd backend
python -m pytest app/tests/ -v
```

Coverage: auth flows, RBAC enforcement, IDOR protection, JWT tamper resistance, mass assignment, Stripe webhook validation, payment lifecycle, file upload validation.

---

## Branching Strategy

```
main        ← production; only merged from dev via PR
dev         ← integration branch; all feature branches target this
feature/*   ← new features
fix/*       ← bug fixes
```

Branch off `dev`, open a PR against `dev`. PRs to `main` are cut from `dev` at release time.

Pre-commit hooks enforce ruff lint + format on every commit. Run `pre-commit install` after cloning.

---

## Deployment

### Backend — Fly.io

```bash
cd backend
flyctl deploy
```

Set secrets (never committed to the repo):

```bash
flyctl secrets set \
  SECRET_KEY=... \
  DATABASE_URL=... \
  GOOGLE_API_KEY=... \
  GROQ_API_KEY=... \
  CLOUDFLARE_R2_ACCOUNT_ID=... \
  CLOUDFLARE_R2_ACCESS_KEY_ID=... \
  CLOUDFLARE_R2_SECRET_ACCESS_KEY=... \
  STRIPE_SECRET_KEY=... \
  STRIPE_WEBHOOK_SECRET=... \
  ADMIN_INVITE_CODE=...
```

The app runs in the Johannesburg (`jnb`) region. See `backend/fly.toml` for machine sizing and concurrency config.

### Frontend — Vercel

Connect the GitHub repo to Vercel, set root directory to `frontend`, and add:

```
NEXT_PUBLIC_API_URL=https://your-fly-app.fly.dev/api/v1
```

### Database migrations

Migrations run automatically on container startup (`alembic upgrade head`). To generate a new migration after a model change:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe the change"
```

Always review autogenerated migrations before committing — Alembic misses some operations (column type changes, constraint modifications). Use `text()` for all `server_default` values on JSONB or non-trivial types to avoid PostgreSQL DDL errors.

---

## AI Pipeline

Diagnosis requests are processed asynchronously via Celery:

1. Patient uploads 1–5 images → stored in R2, presigned URLs generated
2. Celery task fetches images via presigned URL → sends to Gemini Vision
3. Gemini returns structured JSON: modality, summary, findings, impression, differential diagnoses, recommendations, urgency (`routine` / `urgent` / `emergent`), confidence score
4. On Gemini failure, Groq Llama 3.3 70b is tried as fallback
5. Diagnosis record updated → `ai_complete`; patient notified by email
6. Doctor reviews, adds notes, overrides if needed → `reviewed`

Supported modalities: chest X-ray, fundus photography, dermatology, brain MRI, mammography.

---

## Security

A full OWASP-aligned security audit has been completed. Key protections:

- **IDOR:** all resource queries are ownership-scoped at the SQL level
- **JWT:** `algorithms=["HS256"]` explicitly set; role is re-read from the DB on each request, not trusted from the token payload
- **Mass assignment:** `Literal["patient", "doctor"]` on registration role field; the admin role is only assignable via the invite-code-protected `/auth/admin/register` endpoint
- **Admin access:** admin accounts cannot be self-registered without a server-side invite code; the code is never stored in the DB
- **Webhook integrity:** Stripe HMAC signature verified before any state change
- **Rate limiting:** slowapi per-JWT-subject for authenticated requests, per-IP for public endpoints
- **Confirmation dialogs:** all destructive frontend actions (cancel appointment, delete account, admin ban/delete) require explicit user confirmation before the API call is made
- **Refresh token rotation:** each refresh issues a new token and invalidates the old one

See [SECURITY.md](SECURITY.md) for the complete audit report and accepted risks.

---

## License

Proprietary. All rights reserved.
