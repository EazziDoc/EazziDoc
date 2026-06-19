# EazziDoc

AI-powered medical imaging diagnostics platform built for underserved communities across Africa. Patients upload medical images (X-ray, MRI, fundus, skin, mammography), receive a structured AI diagnostic report within minutes, and book a consultation with a verified doctor — all from a single interface.

> **Status:** Active development. Core product shipped. Admin dashboard and specialist ML models in progress. See [ROADMAP](docs/ROADMAP.md).

---

## Architecture

```
Browser (Next.js 14)
    │
    ▼
FastAPI (Uvicorn)          ← REST API, JWT auth, rate limiting
    │
    ├── PostgreSQL          ← Primary store (SQLAlchemy 2.0 async + asyncpg)
    ├── Redis               ← Celery broker + result backend
    ├── Celery Worker       ← AI pipeline tasks (image analysis)
    └── Cloudflare R2       ← Medical image storage (S3-compatible, presigned URLs)

AI Pipeline (Celery task):
    Gemini 2.0 Flash Vision → structured report
    Groq Llama 3.3 70b      ← fallback for unknown modalities
```

The API and worker share the same Docker image. The frontend is a separate Next.js app deployed independently on Vercel. There is no server-side rendering of application data — the frontend is a pure SPA communicating with the API over HTTPS.

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
| Monitoring | Sentry (errors) + Prometheus + Grafana | Structured JSON logs in production |
| Deployment | Fly.io (API) · Vercel (frontend) | Johannesburg region primary |

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
SMTP_HOST=                # leave blank to skip emails in dev
GOOGLE_API_KEY=           # Gemini — required for AI pipeline
GROQ_API_KEY=             # Groq fallback — required for AI pipeline
CLOUDFLARE_R2_ACCOUNT_ID=
CLOUDFLARE_R2_ACCESS_KEY_ID=
CLOUDFLARE_R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_BUCKET_NAME=
STRIPE_SECRET_KEY=        # Stripe test key — required for payments
```

### 2. Start the backend

```bash
docker compose up --build
```

This starts Postgres, Redis, the API server, and the Celery worker. Alembic migrations run automatically on startup.

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The `backend/app/` directory is volume-mounted into the container. Uvicorn runs with `--reload`, so code changes take effect immediately without rebuilding.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3001 (or 3000 if available).

---

## Project Structure

```
EazziDoc/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Route handlers (auth, patients, doctors,
│   │   │                    #   diagnoses, appointments, payments, admin)
│   │   ├── core/            # Config, DB session, JWT, dependencies,
│   │   │                    #   rate limiter, Celery app, metrics
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic (AI pipeline, email,
│   │   │                    #   storage, payments)
│   │   └── tests/           # pytest integration test suite
│   ├── alembic/             # Database migrations
│   ├── Dockerfile           # Multi-stage build (builder + production)
│   └── pyproject.toml       # Dependencies (base, ml, prod, dev extras)
│
├── frontend/
│   ├── app/                 # Next.js App Router pages
│   │   ├── (auth)/          # Login, register
│   │   └── (dashboard)/     # Patient, doctor, admin views
│   ├── components/          # Shared UI components
│   └── lib/                 # API client, auth context, types, utils
│
├── docker-compose.yml        # Local development stack
├── docker-compose.monitoring.yml  # Prometheus + Grafana
├── SECURITY.md              # Security audit findings
└── docs/
    └── ROADMAP.md           # Feature roadmap and status
```

---

## Environment Variables

Full reference in `backend/.env.example`. Key groups:

| Group | Variables | Notes |
|---|---|---|
| Database | `DATABASE_URL` | asyncpg connection string |
| Auth | `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | |
| Storage | `CLOUDFLARE_R2_*` | S3-compatible; presigned URLs only, no public access |
| AI | `GOOGLE_API_KEY`, `GROQ_API_KEY` | Both required for full pipeline |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | SSL on 465 or STARTTLS on 587 |
| Payments | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `CONSULTATION_FEE_CENTS` | |
| Monitoring | `SENTRY_DSN` | Optional; omit to disable |

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

The test suite covers: auth flows, RBAC enforcement, IDOR protection, JWT tamper resistance, mass assignment, Stripe webhook validation, and payment lifecycle. See `SECURITY.md` for the full audit report.

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

Set secrets once (never committed):

```bash
flyctl secrets set \
  SECRET_KEY=... \
  DATABASE_URL=... \
  GOOGLE_API_KEY=... \
  GROQ_API_KEY=... \
  CLOUDFLARE_R2_SECRET_ACCESS_KEY=... \
  STRIPE_SECRET_KEY=... \
  STRIPE_WEBHOOK_SECRET=...
```

The app runs in Johannesburg (`jnb`) for latency reasons. See `backend/fly.toml` for machine sizing and concurrency limits.

### Frontend — Vercel

Connect the GitHub repo to Vercel, set root directory to `frontend`, and add `NEXT_PUBLIC_API_URL=https://your-fly-app.fly.dev/api/v1` as an environment variable.

### Database migrations

Migrations run automatically on container startup (`alembic upgrade head`). To generate a new migration after a model change:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe the change"
```

Always review autogenerated migrations before committing — Alembic misses some operations (column type changes, constraint modifications).

---

## AI Pipeline

Diagnosis requests are processed asynchronously via Celery:

1. Patient uploads 1–5 images → stored in R2, presigned URLs generated
2. Celery task fetches images via presigned URL → sends to Gemini Vision
3. Gemini returns structured JSON: modality, summary, findings, impression, differential diagnoses, recommendations, urgency (`routine` / `urgent` / `emergent`), confidence score
4. On Gemini failure, Groq Llama 3.3 70b is tried as fallback
5. Diagnosis record updated → `ai_complete`; patient notified by email
6. Doctor reviews, overrides if needed → `reviewed`

Supported modalities: chest X-ray, fundus photography, dermatology, brain MRI, mammography.

---

## Security

A full OWASP-aligned security audit has been completed. Key protections:

- **IDOR:** all resource queries are ownership-scoped at the SQL level
- **JWT:** `algorithms=["HS256"]` explicitly set; role is read from DB, not token payload
- **Mass assignment:** `Literal["patient", "doctor"]` on registration role field; admin self-registration rejected at 422
- **Webhook integrity:** Stripe HMAC verified before any state change
- **Rate limiting:** slowapi, per-JWT-subject for authenticated requests

See [SECURITY.md](SECURITY.md) for the complete audit report and accepted risks.

---

## License

Proprietary. All rights reserved.
