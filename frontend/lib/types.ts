export type Role = "patient" | "doctor" | "admin";

export interface User {
  id: string;
  email: string;
  role: Role;
  is_verified: boolean;
  is_active: boolean;
  first_name: string | null;
  last_name: string | null;
}

export interface PatientProfile {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  gender: string | null;
  phone: string | null;
  country: string | null;
  medical_history: Record<string, unknown>;
  identity_verification_status: "unverified" | "pending_review" | "verified" | "rejected";
  id_type: string | null;
  id_rejection_reason: string | null;
  id_verified_at: string | null;
}

export interface DoctorProfile {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  specialty: string | null;
  license_number: string | null;
  is_verified: boolean;
  is_available: boolean;
  qualifications: string[];
  other_qualifications: string | null;
  registration_status: "pending_review" | "approved" | "rejected";
  rejection_reason: string | null;
}

export interface DiagnosisReport {
  summary?: string;
  findings?: string[];
  impression?: string;
  differential_diagnoses?: string[];
  recommendations?: string[];
  urgency?: "routine" | "urgent" | "emergent";
  patient_notes?: string;
  error?: string;
}

export interface Diagnosis {
  id: string;
  patient_id: string;
  reviewing_doctor_id: string | null;
  uploaded_by_role: "patient" | "doctor";
  uploading_doctor_id: string | null;
  image_keys: string[];
  modality: string | null;
  model_used: string | null;
  confidence_score: number | null;
  report: DiagnosisReport;
  status: string;
  doctor_notes: string | null;
  treatment_plan: string | null;
  referral: string | null;
  created_at: string;
  updated_at: string;
}

export interface DoctorPatientView {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  gender: string | null;
  phone: string | null;
  country: string | null;
  identity_verification_status: string | null;
  diagnoses: Diagnosis[];
}

export interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  diagnosis_id: string | null;
  scheduled_at: string;
  duration_mins: number;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImageUploadItem {
  image_key: string;
  presigned_url: string;
  size_bytes: number;
  content_type: string;
}

export interface BatchUploadResponse {
  uploaded: ImageUploadItem[];
  total: number;
}

export interface AuditLogItem {
  id: string;
  actor_id: string;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: string;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminDiagnosisDetail {
  id: string;
  patient_id: string;
  patient_name: string | null;
  patient_email: string | null;
  modality: string | null;
  status: string;
  model_used: string | null;
  confidence_score: number | null;
  urgency: string | null;
  image_keys: string[];
  report: DiagnosisReport | null;
  doctor_notes: string | null;
  created_at: string;
  updated_at: string;
  doctor_reviewed_at: string | null;
}
