export type Role = "patient" | "doctor";

export interface User {
  id: string;
  email: string;
  role: Role;
  is_verified: boolean;
  is_active: boolean;
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
  image_keys: string[];
  modality: string | null;
  model_used: string | null;
  confidence_score: number | null;
  report: DiagnosisReport;
  status: string;
  doctor_notes: string | null;
  created_at: string;
  updated_at: string;
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
