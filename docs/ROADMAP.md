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
Admin login is separated from patient/doctor login — `/admin/login` uses a dark-themed portal distinct from `/login`.

**Branches:** `feature/admin-dashboard`, `feature/doctor-credentials`

### Backend

| Endpoint | Purpose |
|---|---|
| `GET /admin/stats/overview` | Platform-level KPIs snapshot |
| `GET /admin/stats/diagnoses` | Diagnosis volume, modality breakdown, AI performance |
| `GET /admin/stats/appointments` | Booking funnel, completion rate, cancellation rate |
| `GET /admin/users` | Paginated user list with filters (role, verified, active) |
| `GET /admin/users/{id}` | Full user detail — profile + diagnosis history + appointments |
| `PATCH /admin/users/{id}` | Activate/deactivate, verify doctor, change role |
| `GET /admin/diagnoses` | All diagnoses — filterable by status/modality/urgency/date |
| `GET /admin/diagnoses/{id}` | Full diagnosis detail with AI report and patient info |
| `POST /admin/diagnoses/{id}/requeue` | Manually re-trigger Celery pipeline for a failed diagnosis |
| `GET /admin/queue/health` | Celery queue depth, active workers, failed/retry task counts |
| `GET /admin/audit-logs` | Immutable audit log of all admin actions, filterable by action type |
| `GET /admin/doctors` | List all doctor registrations — filterable by status |
| `GET /admin/doctors/{id}` | Full doctor registration detail including presigned certification URLs |
| `POST /admin/doctors/{id}/approve` | Approve doctor; sets `is_verified=True`, `registration_status=approved` |
| `POST /admin/doctors/{id}/reject` | Reject doctor with mandatory reason; sets `registration_status=rejected` |

### Frontend pages

| Route | What it shows |
|---|---|
| `/admin/login` | Separate dark-themed admin portal login (rejects non-admin accounts) |
| `/admin` | Dashboard overview — KPI cards, quick links |
| `/admin/users` | User table with search/filter + quick actions (verify, deactivate) |
| `/admin/diagnoses` | Diagnosis table with filters |
| `/admin/diagnoses/[id]` | Full AI report + doctor review + re-queue button |
| `/admin/queue` | Celery queue health — worker status, task counts |
| `/admin/audit-logs` | Paginated audit log with action filter and color-coded badges |
| `/admin/doctors` | Doctor registration list — filter by pending/approved/rejected |
| `/admin/doctors/[id]` | Full registration detail, cert download, approve/reject actions, print-to-PDF export |

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

## Phase 3b — Doctor Registration Approval Workflow 🔄

Doctors must submit credentials at registration and be approved by an admin before patients can book with them.

**Branch:** `feature/doctor-credentials`

### Doctor registration flow
1. Doctor fills step 1: name, email, password (same as before).
2. Doctor fills step 2: specialty, licence number, qualifications (multi-select from catalogue + free-text), certification document upload (PDF/JPG/PNG, up to 5 files, 10 MB each).
3. After submit: auto-login → cert upload → redirect to `/doctor/pending` (pending review page).
4. Admin reviews at `/admin/doctors` and approves or rejects (with reason).
5. Doctor sees their status and rejection reason at `/doctor/pending`.

### Qualification catalogue (multi-select checkboxes)

**African councils & colleges:**
- MDCN (Medical and Dental Council of Nigeria)
- HPCSA (Health Professions Council of South Africa)
- Medical Council of Ghana (MCG)
- Kenya Medical Practitioners & Dentists Council (KMPDC)
- Medical Council of Uganda
- Tanzania Medical Council (TMC)
- Ethiopian Medical Council (EMC)
- West African College of Physicians (WACP) / Fellow (FWACP)
- West African College of Surgeons (WACS) / Fellow (FWACS)
- College of Medicine of South Africa (CMSA)

**Undergraduate degrees:** MBBS, MBChB, MD, DO, BDS, MBBCh

**Postgraduate:** PhD, MSc (Clinical), MPH, MMed

**UK Royal Colleges:** MRCP, MRCS, FRCP, FRCS, MRCGP, FRCR, FRCOG

**USA boards:** ABMS Board Certification, FACP, FACS, FACOG, FACR

**International:** EBMS, FCFP (Canada), WHO Fellowship, Commonwealth Medical Fellowship

### Doctor model additions
```
qualifications        JSONB      list of selected credential strings
other_qualifications  TEXT       free-text for unlisted qualifications
certification_keys    JSONB      R2 object keys for uploaded cert documents
registration_status   VARCHAR    pending_review | approved | rejected (default: pending_review)
rejection_reason      TEXT       admin rejection note shown to doctor
reviewed_at           TIMESTAMP  when admin took action
```

### Certification storage
- Endpoint: `POST /doctors/me/certifications` (multipart upload, requires auth)
- Allowed types: PDF, JPEG, PNG
- Max: 5 files, 10 MB each
- Stored at: `certifications/{user_id}/{uuid}.{ext}` in Cloudflare R2
- Admin access: presigned GET URLs (1 h TTL) returned by `GET /admin/doctors/{id}`

### PDF export
Client-side print: the admin detail page at `/admin/doctors/[id]` has `@media print` CSS and an "Export PDF / Print" button that calls `window.print()`. No server-side PDF generation needed.

---

## Phase 3c — Dark Mode 📋

System/manual dark mode toggle across all pages — patient, doctor, and admin portals.

**Branch:** `feature/dark-mode`

### Implementation
- **Library:** `next-themes` with `ThemeProvider`
- **Tailwind:** `darkMode: "class"` in `tailwind.config.ts`
- **Storage:** user preference persisted in `localStorage` via next-themes
- **Toggle:** theme toggle button in the sidebar and admin nav for all roles
- **Scope:** all pages — auth pages, patient dashboard, doctor dashboard, admin dashboard

### Tailwind dark variants applied to
- Shared components: `Card`, `Button`, `Input`, sidebar
- Auth pages: login, register, admin login
- All dashboard pages (patient, doctor, admin)
- Landing page

---

## Phase 3d — Account Management & Moderation 🔄

Admin-side moderation controls and user-initiated account deletion, plus confirmation dialogs on destructive actions.

**Branch:** `feature/account-management`

### Admin moderation (admin portal)

| Endpoint | Method | Description |
|---|---|---|
| `POST /admin/users/{id}/ban` | admin | Set `is_active=False`, log `user.banned` audit event |
| `POST /admin/users/{id}/unban` | admin | Set `is_active=True`, log `user.unbanned` audit event |
| `DELETE /admin/users/{id}` | admin | Hard delete user row; diagnosis records retained; log `user.deleted` |

- Admins **cannot** ban or delete other admin accounts (guarded at API level)
- Admins **cannot** ban/delete their own account
- All moderation actions are logged to the audit trail
- Frontend: ban / unban / delete buttons on the Users table with confirmation dialogs per action

### Self-service account deletion

| Endpoint | Method | Description |
|---|---|---|
| `DELETE /patients/me` | patient | Soft-delete: sets `is_active=False`, logs out user |
| `DELETE /doctors/me` | doctor | Soft-delete: sets `is_active=False`, logs out user |

- Diagnosis history is **preserved** for medical record compliance
- `RefreshToken` rows are cascade-deleted (user is immediately logged out on all devices)
- Account deletion is available from the **Settings** page under a "Danger zone" section
- Confirmation dialog required before deletion

### Confirmation dialogs

Reusable `ConfirmDialog` component (`components/ui/confirm-dialog.tsx`) using native `<dialog>` element:

- **Appointment cancellation** — patient and doctor appointment pages both prompt before calling cancel API
- **Account deletion** — patient and doctor settings pages both show dialog before calling delete API
- **Admin ban** — confirmation before banning a user
- **Admin delete** — separate stricter confirmation before permanent deletion

---

## Phase 3f — Patient Identity Verification 🔄

Patients verify their identity by submitting a government-issued ID after registration. Admin reviews and approves or rejects.

**Branch:** `feature/patient-verification`

### Patient flow
1. After registration, a banner on the patient dashboard prompts identity verification.
2. Patient goes to **Settings → Identity verification**, selects ID type, enters ID number, and uploads a document scan (PDF, JPEG, or PNG, max 10 MB).
3. Status changes to `pending_review`. Banner updates to "under review".
4. If rejected by admin, banner shows the rejection reason with a **Resubmit →** link.
5. Once approved, banner shows a green "Identity verified" confirmation.

### Identity status lifecycle
`unverified` → `pending_review` → `verified` | `rejected` → `pending_review` (on resubmit)

Approving a patient's identity also sets `user.is_verified = True`.

### New fields on `patients` table
| Column | Type | Description |
|---|---|---|
| `id_type` | VARCHAR(30) | `national_id` \| `passport` \| `drivers_license` |
| `id_number` | VARCHAR(100) | The ID number as entered by the patient |
| `id_document_key` | VARCHAR(500) | R2 object key for the uploaded document |
| `identity_verification_status` | VARCHAR(20) | `unverified` \| `pending_review` \| `verified` \| `rejected` |
| `id_rejection_reason` | TEXT | Admin rejection note shown to the patient |
| `id_verified_at` | TIMESTAMP | When admin approved |

### Backend endpoints
| Endpoint | Role | Description |
|---|---|---|
| `POST /patients/me/identity` | patient | Submit ID type, number, and document (multipart) |
| `POST /admin/users/{id}/verify-identity` | admin | Approve identity; sets `is_verified=True`, logs audit |
| `POST /admin/users/{id}/reject-identity` | admin | Reject with reason; patient can resubmit |

### Document storage
- Stored at: `identity/{user_id}/{uuid}.{ext}` in Cloudflare R2
- Old document replaced on resubmission (best-effort delete of prior key)
- Accepted types: PDF, JPEG, PNG

### Admin Users page changes
- Identity status badge shown in the Verified column for patient rows
- **Verify ID** and **Reject ID** buttons appear for patients with `pending_review` status
- Reject dialog requires a reason before submission

---

## Phase 3e — Admin Registration 🔄

Invite-code-gated admin account creation, replacing the manual SQL promotion workflow.

**Branch:** `feature/admin-registration`

### How it works

1. Admin navigates to `/admin/register` (linked from the admin login page)
2. Fills in name, email, password, and a secret **invite code**
3. Backend validates the code against `ADMIN_INVITE_CODE` env var
4. On success, account is created with `role=admin`, `is_verified=True`, and the user is redirected to `/admin/login` with a success banner

### Security model

- If `ADMIN_INVITE_CODE` is empty or unset, the endpoint returns `403` — registration is fully disabled
- The invite code is never stored in the database; it only lives in the environment
- Rotate the code any time by updating the env var (existing admin accounts are unaffected)
- Wrong code returns the same `403` error as a disabled feature (no information leak about whether feature is on)

### Environment

| Variable | Required | Description |
|---|---|---|
| `ADMIN_INVITE_CODE` | Yes (for registration) | Secret passphrase; leave empty to disable endpoint |

**Local:** set in `backend/.env`
**Production (Fly.io):** `fly secrets set ADMIN_INVITE_CODE=your-secret`

### Backend

- `POST /auth/admin/register` — new endpoint in `app/api/v1/auth.py`
- `AdminRegisterRequest` schema in `app/schemas/auth.py` (same password strength rules as regular registration)

### Frontend

- `/admin/register` — dark-themed form matching the admin portal aesthetic; invite code field styled as password input
- `/admin/login` — green success banner on redirect from registration; "Register with invite code" link in footer

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
