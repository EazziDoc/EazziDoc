"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import {
  doctorCreateDiagnosis,
  doctorGetPatient,
  reviewDiagnosis,
  uploadImages,
} from "@/lib/api";
import type { Diagnosis } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { formatDate, formatDateTime, statusColor } from "@/lib/utils";

const urgencyColor: Record<string, string> = {
  routine: "bg-green-100 text-green-800",
  urgent: "bg-orange-100 text-orange-800",
  emergent: "bg-red-100 text-red-800",
};

const REVIEW_STATUSES = [
  { value: "confirmed", label: "Confirm AI report" },
  { value: "overridden", label: "Override AI report" },
  { value: "flagged", label: "Flag for second opinion" },
  { value: "under_review", label: "Keep under review" },
] as const;

function DiagnosisRow({ dx, patientId }: { dx: Diagnosis; patientId: string }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [notes, setNotes] = useState(dx.doctor_notes ?? "");
  const [treatmentPlan, setTreatmentPlan] = useState(dx.treatment_plan ?? "");
  const [referral, setReferral] = useState(dx.referral ?? "");
  const [reviewStatus, setReviewStatus] = useState<string>(
    dx.status === "ai_complete" ? "confirmed" : dx.status
  );
  const [formError, setFormError] = useState("");

  const { mutateAsync: submitReview, isPending: reviewing } = useMutation({
    mutationFn: (data: {
      notes: string;
      status: string;
      treatment_plan?: string;
      referral?: string;
    }) => reviewDiagnosis(dx.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doctor-patient", patientId] });
      qc.invalidateQueries({ queryKey: ["queue"] });
    },
  });

  async function handleReview(e: React.FormEvent) {
    e.preventDefault();
    if (!notes.trim()) {
      setFormError("Clinical notes are required.");
      return;
    }
    setFormError("");
    try {
      await submitReview({
        notes: notes.trim(),
        status: reviewStatus,
        treatment_plan: treatmentPlan.trim() || undefined,
        referral: referral.trim() || undefined,
      });
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Review failed");
    }
  }

  const report = dx.report ?? {};
  const isReviewable = ["ai_complete", "under_review"].includes(dx.status);
  const isReviewed = ["confirmed", "overridden", "flagged"].includes(dx.status);

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center justify-between px-5 py-4 bg-white hover:bg-gray-50 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-4">
          <div>
            <p className="font-medium text-gray-900 capitalize text-sm">
              {dx.modality?.replace(/_/g, " ") ?? "Unknown modality"}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">{formatDate(dx.created_at)}</p>
          </div>
          {dx.uploaded_by_role === "doctor" && (
            <Badge className="bg-violet-100 text-violet-700 text-xs">Doctor upload</Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          {report.urgency && (
            <Badge className={urgencyColor[report.urgency] ?? ""}>{report.urgency}</Badge>
          )}
          <Badge className={statusColor(dx.status)}>{dx.status.replace(/_/g, " ")}</Badge>
          <span className="text-gray-300 text-sm">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-5 pb-5 pt-3 bg-gray-50 border-t border-gray-100 space-y-5">
          {/* AI report */}
          {report.summary && (
            <div className="space-y-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                AI Report
              </h4>
              <div className="rounded-lg bg-white border border-gray-100 p-4 space-y-4 text-sm">
                {report.summary && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Summary</p>
                    <p className="text-gray-600 leading-relaxed">{report.summary}</p>
                  </div>
                )}
                {report.impression && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Impression</p>
                    <p className="text-gray-600">{report.impression}</p>
                  </div>
                )}
                {report.findings && report.findings.length > 0 && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Findings</p>
                    <ul className="space-y-1">
                      {report.findings.map((f, i) => (
                        <li key={i} className="flex gap-2 text-gray-600">
                          <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-primary-400" />
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.differential_diagnoses && report.differential_diagnoses.length > 0 && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Differentials</p>
                    <ul className="space-y-1">
                      {report.differential_diagnoses.map((d, i) => (
                        <li key={i} className="text-gray-600">• {d}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.recommendations && report.recommendations.length > 0 && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Recommendations</p>
                    <ul className="space-y-1">
                      {report.recommendations.map((r, i) => (
                        <li key={i} className="text-gray-600">→ {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {dx.confidence_score != null && (
                  <p className="text-xs text-gray-400">
                    Confidence: {Math.round(dx.confidence_score * 100)}%
                    {dx.model_used && ` · ${dx.model_used}`}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Existing clinical decision (if reviewed) */}
          {isReviewed && (dx.doctor_notes || dx.treatment_plan || dx.referral) && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Clinical Decision
              </h4>
              <div className="rounded-lg bg-white border border-gray-100 p-4 space-y-3 text-sm">
                {dx.doctor_notes && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Notes</p>
                    <p className="text-gray-600 whitespace-pre-wrap">{dx.doctor_notes}</p>
                  </div>
                )}
                {dx.treatment_plan && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Treatment plan</p>
                    <p className="text-gray-600 whitespace-pre-wrap">{dx.treatment_plan}</p>
                  </div>
                )}
                {dx.referral && (
                  <div>
                    <p className="font-medium text-gray-700 mb-1">Referral</p>
                    <p className="text-gray-600 whitespace-pre-wrap">{dx.referral}</p>
                  </div>
                )}
                {dx.doctor_notes && (
                  <p className="text-xs text-gray-400">
                    Reviewed {dx.updated_at ? formatDateTime(dx.updated_at) : ""}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Review / update form */}
          {(isReviewable || isReviewed) && (
            <form onSubmit={handleReview} className="space-y-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {isReviewed ? "Update Clinical Decision" : "Review Diagnosis"}
              </h4>

              {/* Decision buttons */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Decision</p>
                <div className="flex flex-wrap gap-2">
                  {REVIEW_STATUSES.map((s) => (
                    <button
                      key={s.value}
                      type="button"
                      onClick={() => setReviewStatus(s.value)}
                      className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                        reviewStatus === s.value
                          ? "bg-primary-600 border-primary-600 text-white"
                          : "border-gray-300 text-gray-600 hover:border-primary-400"
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <Textarea
                id={`notes-${dx.id}`}
                label="Clinical notes (required)"
                placeholder="Clinical assessment, corrections, observations…"
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                required
              />

              <Textarea
                id={`treatment-${dx.id}`}
                label="Treatment plan (optional)"
                placeholder="Medications, procedures, lifestyle changes, follow-up schedule…"
                rows={3}
                value={treatmentPlan}
                onChange={(e) => setTreatmentPlan(e.target.value)}
              />

              <Textarea
                id={`referral-${dx.id}`}
                label="Referral (optional)"
                placeholder="e.g. Refer to cardiologist at Lagos University Teaching Hospital for echocardiogram…"
                rows={2}
                value={referral}
                onChange={(e) => setReferral(e.target.value)}
              />

              {formError && (
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</p>
              )}

              <Button type="submit" loading={reviewing} size="sm">
                {isReviewed ? "Update decision" : "Submit review"}
              </Button>
            </form>
          )}

          {/* Pending/processing state */}
          {["pending", "processing"].includes(dx.status) && (
            <p className="text-sm text-gray-400 italic">
              AI analysis in progress — review will be available once complete.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function DoctorPatientDetailPage() {
  const { id: patientId } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const [showUpload, setShowUpload] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadNotes, setUploadNotes] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["doctor-patient", patientId],
    queryFn: () => doctorGetPatient(patientId),
  });

  const { mutateAsync: createDx } = useMutation({
    mutationFn: (imageKeys: string[]) =>
      doctorCreateDiagnosis(patientId, {
        image_keys: imageKeys,
        patient_notes: uploadNotes.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doctor-patient", patientId] });
      setShowUpload(false);
      setUploadFiles([]);
      setUploadNotes("");
      setUploadError("");
    },
  });

  async function handleUploadSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFiles.length) {
      setUploadError("Select at least one image.");
      return;
    }
    setUploading(true);
    setUploadError("");
    try {
      const { uploaded } = await uploadImages(uploadFiles);
      const keys = uploaded.map((u) => u.image_key);
      await createDx(keys);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-24 text-gray-400">
        Patient not found.{" "}
        <Link href="/doctor/patients" className="text-primary-600 hover:underline">
          Back
        </Link>
      </div>
    );
  }

  const fullName = `${data.first_name} ${data.last_name}`;

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Link
            href="/doctor/patients"
            className="text-sm text-gray-400 hover:text-gray-600 mt-1"
          >
            ←
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{fullName}</h1>
            <p className="text-gray-400 text-sm mt-0.5">
              {data.gender ? `${data.gender.replace("_", " ")} · ` : ""}
              {data.country ?? ""}
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowUpload((v) => !v)}
          className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 whitespace-nowrap"
        >
          {showUpload ? "Cancel" : "+ Upload scan"}
        </button>
      </div>

      {/* Patient info card */}
      <Card>
        <CardHeader>
          <CardTitle>Patient profile</CardTitle>
        </CardHeader>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Date of birth</dt>
            <dd className="mt-1 text-gray-900">
              {data.date_of_birth ? formatDate(data.date_of_birth) : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Phone</dt>
            <dd className="mt-1 text-gray-900">{data.phone ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Country</dt>
            <dd className="mt-1 text-gray-900">{data.country ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Identity status</dt>
            <dd className="mt-1">
              {data.identity_verification_status ? (
                <Badge
                  className={
                    data.identity_verification_status === "verified"
                      ? "bg-green-100 text-green-700"
                      : data.identity_verification_status === "pending_review"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-gray-100 text-gray-600"
                  }
                >
                  {data.identity_verification_status.replace("_", " ")}
                </Badge>
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>
      </Card>

      {/* Upload scan form */}
      {showUpload && (
        <Card>
          <CardHeader>
            <CardTitle>Upload scan for {data.first_name}</CardTitle>
          </CardHeader>
          <form onSubmit={handleUploadSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Medical images (1–5 files, max 10 MB each)
              </label>
              <div
                className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-primary-400 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                {uploadFiles.length > 0 ? (
                  <div className="space-y-1">
                    {uploadFiles.map((f, i) => (
                      <p key={i} className="text-sm text-gray-700">
                        {f.name} ({(f.size / 1024 / 1024).toFixed(1)} MB)
                      </p>
                    ))}
                    <p className="text-xs text-gray-400 mt-2">Click to change</p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-gray-500">Click to select images</p>
                    <p className="text-xs text-gray-400 mt-1">DICOM, JPEG, PNG, TIFF</p>
                  </div>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*,.dcm"
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []).slice(0, 5);
                  setUploadFiles(files);
                }}
              />
            </div>

            <Textarea
              id="upload-notes"
              label="Clinical notes / context (optional)"
              placeholder="Reason for scan, relevant history, suspected findings…"
              rows={3}
              value={uploadNotes}
              onChange={(e) => setUploadNotes(e.target.value)}
            />

            {uploadError && (
              <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{uploadError}</p>
            )}

            <p className="text-xs text-gray-400">
              The scan will be analysed by AI immediately. {data.first_name} will be notified by
              email.
            </p>

            <Button type="submit" loading={uploading} disabled={!uploadFiles.length}>
              {uploading ? "Uploading…" : "Upload & start analysis"}
            </Button>
          </form>
        </Card>
      )}

      {/* Diagnosis history */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Diagnosis history</h2>
          <span className="text-sm text-gray-400">{data.diagnoses.length} total</span>
        </div>

        {data.diagnoses.length === 0 ? (
          <Card>
            <p className="text-center text-gray-400 py-8 text-sm">
              No diagnoses yet. Upload the first scan above.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {data.diagnoses.map((dx) => (
              <DiagnosisRow key={dx.id} dx={dx} patientId={patientId} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
