import type {
  Appointment,
  BatchUploadResponse,
  Diagnosis,
  DoctorProfile,
  PatientProfile,
  User,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// In-memory access token — never touches localStorage
let _accessToken: string | null = null;

export function setAccessToken(t: string | null) {
  _accessToken = t;
}

export function getAccessToken() {
  return _accessToken;
}

// ── core fetch wrapper ────────────────────────────────────────────────────────

async function req<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (_accessToken) headers["Authorization"] = `Bearer ${_accessToken}`;

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: "include", // send httpOnly refresh cookie
  });

  // Attempt token refresh on 401 then retry once
  if (res.status === 401 && retry) {
    const refreshed = await refreshToken();
    if (refreshed) return req<T>(path, options, false);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

// ── auth ──────────────────────────────────────────────────────────────────────

export async function register(data: {
  email: string;
  password: string;
  role: "patient" | "doctor";
  first_name: string;
  last_name: string;
}) {
  return req<{ user_id: string; email: string; role: string }>(
    "/auth/register",
    { method: "POST", body: JSON.stringify(data) },
  );
}

export async function login(email: string, password: string) {
  const data = await req<{ access_token: string; token_type: string }>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
  setAccessToken(data.access_token);
  return data;
}

export async function refreshToken(): Promise<boolean> {
  try {
    const data = await req<{ access_token: string }>(
      "/auth/refresh",
      { method: "POST" },
      false, // don't retry refresh on failure
    );
    setAccessToken(data.access_token);
    return true;
  } catch {
    setAccessToken(null);
    return false;
  }
}

export async function logout() {
  await req("/auth/logout", { method: "POST" }).catch(() => {});
  setAccessToken(null);
}

export async function getMe() {
  return req<User>("/auth/me");
}

// ── profiles ──────────────────────────────────────────────────────────────────

export async function getPatientProfile() {
  return req<PatientProfile>("/patients/me");
}

export async function updatePatientProfile(data: Partial<PatientProfile>) {
  return req<PatientProfile>("/patients/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getDoctorProfile() {
  return req<DoctorProfile>("/doctors/me");
}

export async function updateDoctorProfile(data: Partial<DoctorProfile>) {
  return req<DoctorProfile>("/doctors/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function listAvailableDoctors() {
  return req<DoctorProfile[]>("/doctors");
}

// ── uploads ───────────────────────────────────────────────────────────────────

export async function uploadImages(files: File[]) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return req<BatchUploadResponse>("/uploads/images", {
    method: "POST",
    body: form,
  });
}

// ── diagnoses ─────────────────────────────────────────────────────────────────

export async function createDiagnosis(data: {
  image_keys: string[];
  patient_notes?: string;
}) {
  return req<Diagnosis>("/diagnoses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listDiagnoses() {
  return req<Diagnosis[]>("/diagnoses");
}

export async function getDiagnosis(id: string) {
  return req<Diagnosis>(`/diagnoses/${id}`);
}

export async function getPendingQueue() {
  return req<Diagnosis[]>("/diagnoses/queue/pending");
}

export async function reviewDiagnosis(
  id: string,
  data: { notes: string; status: string },
) {
  return req<Diagnosis>(`/diagnoses/${id}/review`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ── appointments ──────────────────────────────────────────────────────────────

export async function bookAppointment(data: {
  doctor_id: string;
  scheduled_at: string;
  duration_mins?: number;
  notes?: string;
  diagnosis_id?: string;
}) {
  return req<Appointment>("/appointments", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listAppointments() {
  return req<Appointment[]>("/appointments");
}

export async function cancelAppointment(id: string) {
  return req<Appointment>(`/appointments/${id}/cancel`, { method: "PATCH" });
}

export async function listDoctorAppointments() {
  return req<Appointment[]>("/doctor/appointments");
}

export async function confirmAppointment(id: string) {
  return req<Appointment>(`/doctor/appointments/${id}/confirm`, {
    method: "PATCH",
  });
}

export async function completeAppointment(id: string) {
  return req<Appointment>(`/doctor/appointments/${id}/complete`, {
    method: "PATCH",
  });
}

export async function doctorCancelAppointment(id: string) {
  return req<Appointment>(`/doctor/appointments/${id}/cancel`, {
    method: "PATCH",
  });
}

// ── admin ─────────────────────────────────────────────────────────────────────

export interface OverviewStats {
  total_users: number;
  total_patients: number;
  total_doctors: number;
  verified_doctors: number;
  total_diagnoses: number;
  pending_diagnoses: number;
  ai_complete_diagnoses: number;
  failed_diagnoses: number;
  total_appointments: number;
  new_users_30d: number;
  new_diagnoses_30d: number;
}

export interface DiagnosisStats {
  by_modality: { modality: string; count: number }[];
  by_status: { status: string; count: number }[];
  by_model: { model_used: string; count: number }[];
  by_urgency: { urgency: string; count: number }[];
  avg_confidence: number | null;
  avg_time_to_ai_secs: number | null;
  avg_time_to_review_secs: number | null;
  override_rate: number | null;
}

export interface AppointmentStats {
  total: number;
  booked: number;
  confirmed: number;
  completed: number;
  cancelled: number;
  completion_rate: number | null;
  cancellation_rate: number | null;
  avg_duration_mins: number | null;
}

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
  display_name: string | null;
  specialty?: string | null;
  total_diagnoses?: number;
  total_appointments?: number;
}

export interface AdminUserList {
  users: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminDiagnosis {
  id: string;
  patient_id: string;
  patient_name: string | null;
  modality: string | null;
  status: string;
  model_used: string | null;
  confidence_score: number | null;
  urgency: string | null;
  image_count: number;
  created_at: string;
  doctor_reviewed_at: string | null;
}

export interface AdminDiagnosisList {
  diagnoses: AdminDiagnosis[];
  total: number;
  page: number;
  page_size: number;
}

export interface QueueHealth {
  workers: { name: string; status: string; active_tasks: number; processed: number | null }[];
  active_tasks: number;
  scheduled_tasks: number;
  reserved_tasks: number;
  total_tasks_in_queue: number;
  pending_in_broker: number;
}

export async function adminGetOverview() {
  return req<OverviewStats>("/admin/stats/overview");
}

export async function adminGetDiagnosisStats() {
  return req<DiagnosisStats>("/admin/stats/diagnoses");
}

export async function adminGetAppointmentStats() {
  return req<AppointmentStats>("/admin/stats/appointments");
}

export async function adminListUsers(params?: {
  page?: number;
  role?: string;
  is_active?: boolean;
  search?: string;
}) {
  const q = new URLSearchParams();
  if (params?.page) q.set("page", String(params.page));
  if (params?.role) q.set("role", params.role);
  if (params?.is_active !== undefined) q.set("is_active", String(params.is_active));
  if (params?.search) q.set("search", params.search);
  return req<AdminUserList>(`/admin/users?${q}`);
}

export async function adminGetUser(id: string) {
  return req<AdminUser>(`/admin/users/${id}`);
}

export async function adminUpdateUser(
  id: string,
  data: { is_active?: boolean; is_verified?: boolean; role?: string },
) {
  return req<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function adminListDiagnoses(params?: {
  page?: number;
  status?: string;
  modality?: string;
  urgency?: string;
}) {
  const q = new URLSearchParams();
  if (params?.page) q.set("page", String(params.page));
  if (params?.status) q.set("status", params.status);
  if (params?.modality) q.set("modality", params.modality);
  if (params?.urgency) q.set("urgency", params.urgency);
  return req<AdminDiagnosisList>(`/admin/diagnoses?${q}`);
}

export async function adminRequeueDiagnosis(id: string) {
  return req<{ queued: boolean; diagnosis_id: string }>(`/admin/diagnoses/${id}/requeue`, {
    method: "POST",
  });
}

export async function adminGetQueueHealth() {
  return req<QueueHealth>("/admin/queue/health");
}

// ── doctor: linked patients ───────────────────────────────────────────────────

export async function listMyPatients() {
  return req<PatientProfile[]>("/doctor/patients");
}
