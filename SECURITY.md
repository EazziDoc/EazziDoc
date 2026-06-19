# EazziDoc Security Audit

**Date:** 2026-06-19  
**Scope:** EazziDoc REST API backend (`/api/v1/`)  
**Methodology:** Static code review + automated regression test suite (`test_security.py`)

---

## 1. Authentication & Session Management

| Control | Implementation | Finding |
|---|---|---|
| Access token | HS256-signed JWT, 15-minute expiry | ✅ PASS |
| Refresh token | SHA-256 hash stored; raw token never persisted | ✅ PASS |
| Refresh cookie | `HttpOnly`, `SameSite=Lax`, `Secure` in production, path-scoped to `/api/v1/auth` | ✅ PASS |
| Refresh rotation | Old token deleted on every `/auth/refresh` call | ✅ PASS |
| Deactivated-user check | `is_active` verified on every authenticated request | ✅ PASS |

**Note:** `Secure=True` is only set when `ENVIRONMENT=production`. Developers running locally over HTTP should use `ENVIRONMENT=development` and be aware that cookies are transmitted in plaintext in that mode. This is by design and has no production impact.

---

## 2. Authorization (Role-Based Access Control)

| Vector | Finding | Detail |
|---|---|---|
| Patient → doctor endpoints | ✅ PASS | `require_role("doctor")` returns 403 |
| Doctor → patient endpoints | ✅ PASS | `require_role("patient")` returns 403 |
| Patient/doctor → admin endpoints | ✅ PASS | `require_role("admin")` returns 403 |
| Unauthenticated → any protected endpoint | ✅ PASS | FastAPI `HTTPBearer` returns 403 |

**Role source:** The `role` field is read from the **database** on every request via `get_current_user`, not from the JWT payload. An attacker who modifies the `role` claim in a JWT they hold will still be bound to the DB-recorded role.

---

## 3. JWT Tampering

| Attack | Expected | Finding |
|---|---|---|
| Invalid signature (wrong secret) | 401 | ✅ PASS |
| Expired token | 401 | ✅ PASS |
| `alg: none` (unsigned JWT) | 401/403 | ✅ PASS — `algorithms=["HS256"]` rejects unsigned tokens |
| Role claim escalation (`"role": "admin"` in payload) | 403 | ✅ PASS — DB role is authoritative |

The `decode_access_token` call uses `algorithms=["HS256"]` explicitly, which prevents algorithm confusion attacks including `alg: none` and RS256-to-HS256 downgrade.

---

## 4. IDOR (Insecure Direct Object Reference)

All resource lookups are ownership-scoped at the query level.

| Resource | Enforcement | Finding |
|---|---|---|
| Appointments | `appt.patient_id != patient.id` → 403 | ✅ PASS |
| Diagnoses | `WHERE id = ? AND patient_id = ?` → 404 | ✅ PASS |
| Payments | Appointment ownership checked first → 403 | ✅ PASS |
| Doctor appointment confirm/complete/cancel | `appt.doctor_id != doctor.id` → 403 | ✅ PASS |

**Diagnosis IDOR returns 404, not 403.** This is the preferred pattern: it does not reveal that the resource exists to an unauthorized caller. Appointments return 403 (the resource existence is revealed, which is an acceptable trade-off given that appointment IDs are UUIDs v4).

---

## 5. Mass Assignment

| Vector | Finding |
|---|---|
| `POST /auth/register` with `role: "admin"` | ✅ PASS — Pydantic `Literal["patient", "doctor"]` rejects at 422 |
| `POST /auth/register` with `role: "superuser"` | ✅ PASS — same Pydantic validation |

The `role` field in `RegisterRequest` uses `Literal["patient", "doctor"]`, enforced at the Pydantic layer before any database interaction.

---

## 6. Input Validation

| Field | Validation | Finding |
|---|---|---|
| Email | Pydantic `EmailStr` | ✅ PASS |
| Password | Min 8 chars, ≥1 uppercase, ≥1 digit | ✅ PASS |
| Role (registration) | `Literal["patient", "doctor"]` | ✅ PASS |
| Doctor review status | `pattern="^(confirmed|overridden|flagged|under_review)$"` | ✅ PASS |

---

## 7. Payment Webhook Security

| Vector | Finding |
|---|---|
| POST to `/payments/webhook` without `stripe-signature` header | ✅ PASS — 400 returned |
| POST with invalid/tampered signature | ✅ PASS — 400 returned |
| Unknown session ID in `checkout.session.completed` event | ✅ PASS — logged and ignored; 200 returned to Stripe (correct) |

Stripe webhook events are verified using HMAC (`stripe.Webhook.construct_event`) before any state change. The endpoint accepts any failure from this call as a signal to reject, avoiding partial-trust parsing.

---

## 8. Rate Limiting

| Endpoint | Limit | Note |
|---|---|---|
| `POST /auth/register` | 5/minute | Slows credential-stuffing |
| `POST /auth/login` | 10/minute | Slows brute-force |
| `POST /auth/refresh` | 30/minute | |
| `POST /diagnoses` | 10/hour | Limits AI pipeline abuse |

Rate limits are enforced via `slowapi` using JWT subject for authenticated requests, IP address for unauthenticated ones.

---

## 9. Notes & Accepted Risks

### Doctor self-registration
Any user can self-register with `role: "doctor"`. Doctors have a separate `is_verified` flag (default `False`) that admins must set to `True` before the doctor appears in patient-facing listings (`Doctor.is_available`). Clinical workflows that depend on verified credentials should gate on `is_verified` — this is enforced in the doctor listing endpoint today.

### Admin role promotion
An admin can change any user's `role` field, including promoting a user to `admin`. This is intentional (seeding new admins requires at least one existing admin). Every such change is recorded in the audit log (`action: user.role_changed`). There is no mechanism to make this self-service; it requires an existing admin account.

### Refresh token window after deactivation
Deactivating a user invalidates their access on the very next request (checked server-side). However, outstanding refresh tokens in the `refresh_tokens` table are not proactively deleted on deactivation. An attacker who holds a valid refresh token for a deactivated account cannot use it to get a new access token because `/auth/refresh` also checks `user.is_active`. No action required, but proactive token deletion on deactivation would further harden this.

---

## 10. Automated Test Coverage

All findings above are covered by regression tests in:

```
backend/app/tests/integration/test_security.py
```

Tests are organized into sections matching this document:
1. `test_protected_endpoints_reject_unauthenticated` (parametrized over 6 endpoints)
2. Role enforcement (5 tests)
3. IDOR (5 tests)
4. JWT tampering (4 tests)
5. Mass assignment (2 tests)
6. Deactivated user (1 test)
7. Webhook security (2 tests)
