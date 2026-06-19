# EazziDoc — Product Roadmap

> AI-powered medical imaging diagnostics platform.
> Stack: FastAPI + PostgreSQL + Celery/Redis + Next.js 14 + Cloudflare R2.
> Infrastructure: Fly.io (backend) · Vercel (frontend) · GitHub Actions (CI/CD).

---

## Status key

| Symbol | Meaning |
|--------|---------|
| ✅ | Merged to main |
| 🔄 | In progress |
| 📋 | Planned — next up |
| 🔮 | Planned — future |

---

## Phase 0 — Foundation ✅

Core infrastructure and authentication.

| Feature branch | What shipped |
|---|---|
| `feature/docker-setup` | docker-compose, Postgres, Redis, Celery worker, Alembic |
| `feature/database-schema` | SQLAlchemy models: User, Patient, Doctor, Diagnosis, Appointment, RefreshToken |
| `feature/auth` | JWT access tokens (15 min, in-memory), opaque refresh tokens (SHA-256, 7d, httpOnly cookie), bcrypt passwords |
| `feature/patient-profiles` | Patient and Doctor profile CRUD, role-gated endpoints |
| `feature/initial-migration` | Alembic `0001_initial_schema.py` — all tables in dependency order |

---

## Phase 1 — Core Product ✅

Medical image upload, AI diagnosis pipeline, and appointment booking.

| Feature branch | What shipped |
|---|---|
| `feature/storage` | Cloudflare R2 batch upload (1–5 images), presigned URLs, lazy boto3 client, DICOM/JPEG/PNG/TIFF support |
| `feature/ai-pipeline` | Gemini 2.0 Flash Vision (modality detection + structured report) · Groq Llama 3.3 70b fallback · Celery async task · Diagnoses CRUD |
| `feature/appointments` | Booking, status lifecycle (booked → confirmed → completed · cancel), doctor listing |

**AI report fields:** summary, findings, impression, differential diagnoses, recommendations, urgency (routine/urgent/emergent), confidence score.

**Supported modalities:** chest X-ray, fundus, skin, brain MRI, mammography.

---

## Phase 2 — Frontend ✅

Next.js 14 App Router frontend, deployed on Vercel.

| Feature branch | What shipped |
|---|---|
| `feature/frontend` | Full patient flow (upload → AI report → book appointment) · Doctor flow (review queue + appointment management) · Profile settings for both roles · Landing page · Auth (login/register) · Role-aware sidebar |

**Auth pattern:** access token in-memory (never localStorage), refresh via httpOnly cookie, 401 → auto-refresh → retry.

**Key UX:** diagnosis detail polls every 5 s while `pending`/`processing`, stops when AI finishes.

---

## Phase 3 — Admin Dashboard 🔄

Internal operations and business intelligence panel. Gated to a new `admin` role.

**Branch:** `feature/admin`

### Backend

| Endpoint | Purpose |
|---|---|
| `GET /admin/stats/overview` | Platform-level KPIs snapshot |
| `GET /admin/stats/diagnoses` | Diagnosis volume, modality breakdown, AI performance |
| `GET /admin/stats/appointments` | Booking funnel, completion rate, cancellation rate |
| `GET /admin/stats/doctors` | Per-doctor activity: cases reviewed, avg review time, queue wait |
| `GET /admin/users` | Paginated user list with filters (role, verified, active) |
| `GET /admin/users/{id}` | Full user detail — profile + diagnosis history + appointments |
| `PATCH /admin/users/{id}` | Activate/deactivate, verify doctor, change role |
| `GET /admin/diagnoses` | All diagnoses — filterable by status/modality/urgency/date |
| `POST /admin/diagnoses/{id}/requeue` | Manually re-trigger Celery pipeline for a failed diagnosis |
| `GET /admin/queue/health` | Celery queue depth, active workers, failed/retry task counts |
| `GET /admin/storage/stats` | R2 bucket: total objects, total size, per-patient breakdown |

### Frontend pages

| Route | What it shows |
|---|---|
| `/admin` | Dashboard overview — KPI cards + sparklines |
| `/admin/users` | User table with search/filter + quick actions (verify, deactivate) |
| `/admin/users/[id]` | Full patient or doctor profile + timeline |
| `/admin/diagnoses` | Diagnosis table with filters |
| `/admin/diagnoses/[id]` | Full AI report + doctor review + re-queue button |
| `/admin/queue` | Celery queue health — worker status, task counts, failure log |
| `/admin/storage` | R2 usage summary |

### KPI definitions

**Business-wide**
- Total registered users (all time + 30-day trend)
- Monthly active users (patients + doctors separately)
- Patient : doctor ratio
- New registrations per day (last 30 days chart)
- Doctor verification rate (verified / total doctors)

**Clinical volume**
- Total diagnoses submitted (all time + weekly trend)
- Diagnoses by modality (pie/bar)
- Diagnoses by status (pending / ai_complete / reviewed / failed)
- Daily diagnosis volume (last 30 days chart)
- Avg time from submission to AI complete (p50, p90)
- Avg time from AI complete to doctor review (p50, p90)

**AI quality**
- Avg confidence score per modality
- Confidence score distribution (histogram)
- AI override rate — % of AI reports overridden by doctors
- Urgency distribution (routine / urgent / emergent) by modality
- Failed diagnosis rate (pipeline errors)
- Model usage breakdown (Gemini vs Groq fallback)

**Appointments**
- Total bookings (all time + weekly)
- Booking funnel: booked → confirmed → completed (drop-off at each stage)
- Cancellation rate (patient vs doctor-initiated)
- Avg appointment duration
- Doctor utilisation: cases per doctor per week

**Single patient view**
- Registration date, last active, verification status
- Full diagnosis history (date, modality, status, AI urgency, doctor review outcome)
- Full appointment history (dates, doctors, statuses)
- Storage used (image count + MB)

---

## Phase 4 — Specialist ML Models 🔮

Replace Gemini with fine-tuned open-source models per modality. Hosted on Fly.io GPU workers or Hugging Face Inference Endpoints.

| Modality | Model |
|---|---|
| Chest X-ray | `torchxrayvision` (DenseNet-121, chestxray14) |
| Skin | `derm-foundation` (Google) · ISIC 2024 winner ensemble |
| General radiology | `microsoft/BiomedVLP-CXR-BERT-specialized` |
| Brain MRI | Tumour detection model (Falconsai pattern) |

**Branch:** `feature/ml-models`

Gemini remains as fallback for unknown modalities and graceful degradation.

---

## Phase 5 — Retraining Pipeline 🔮

Close the feedback loop: doctor reviews accumulate → periodic retraining → better models.

**Branch:** `feature/retraining`

- Doctor `confirmed` / `overridden` / `flagged` reviews become labelled training data
- Celery beat job triggers weekly retraining run
- Experiment tracking: Weights & Biases
- Model registry: Hugging Face Hub
- A/B shadow mode: new model runs in parallel, metrics compared before promotion
- Admin dashboard shows retraining history and model version in use per modality

---

## Phase 6 — Production Hardening 🔮

| Area | Work |
|---|---|
| Payments | Stripe integration — subscription tiers for patients, payout for doctors |
| Notifications | Email (Resend) + in-app — diagnosis ready, appointment reminders |
| GDPR / data export | Patient data export endpoint, right-to-erasure flow |
| Audit log | Immutable log of all admin actions |
| Rate limiting | Per-IP and per-user limits on upload and AI endpoints |
| Observability | Sentry (errors) + Prometheus/Grafana (metrics) + structured logging |
| Pentesting | OWASP Top 10 review before public launch |

---

## Deployment targets

| Service | Provider | Region |
|---|---|---|
| Backend API | Fly.io | Johannesburg (`jnb`) |
| Frontend | Vercel | Edge (auto) |
| Database | Fly.io Postgres | Johannesburg |
| Cache / broker | Fly.io Redis | Johannesburg |
| Object storage | Cloudflare R2 | Auto (S3-compatible) |
| CI/CD | GitHub Actions | — |
