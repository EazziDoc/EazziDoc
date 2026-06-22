"use client";

import { use } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { adminGetDiagnosis, adminRequeueDiagnosis } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  ai_complete: "bg-purple-100 text-purple-800",
  reviewed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const URGENCY_COLORS: Record<string, string> = {
  routine: "bg-green-100 text-green-800",
  urgent: "bg-orange-100 text-orange-800",
  emergent: "bg-red-100 text-red-800",
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start gap-4 py-2 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500 shrink-0">{label}</span>
      <span className="text-sm text-gray-900 text-right">{value ?? "—"}</span>
    </div>
  );
}

export default function AdminDiagnosisDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();

  const { data: dx, isLoading } = useQuery({
    queryKey: ["admin-diagnosis", id],
    queryFn: () => adminGetDiagnosis(id),
  });

  const requeue = useMutation({
    mutationFn: () => adminRequeueDiagnosis(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-diagnosis", id] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!dx) {
    return (
      <div className="text-center py-16 text-gray-400">
        Diagnosis not found.{" "}
        <Link href="/admin/diagnoses" className="text-primary-600 hover:underline">
          Back to diagnoses
        </Link>
      </div>
    );
  }

  const canRequeue = dx.status === "failed" || dx.status === "pending";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/admin/diagnoses" className="text-sm text-gray-400 hover:text-gray-600">
              ← Diagnoses
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Diagnosis detail</h1>
          <p className="text-xs font-mono text-gray-400">{dx.id}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold capitalize ${STATUS_COLORS[dx.status] ?? "bg-gray-100 text-gray-800"}`}>
            {dx.status.replace("_", " ")}
          </span>
          {canRequeue && (
            <Button
              size="sm"
              loading={requeue.isPending}
              onClick={() => requeue.mutate()}
            >
              Re-queue
            </Button>
          )}
        </div>
      </div>

      {/* Patient */}
      <Section title="Patient">
        <Card className="divide-y divide-gray-50 py-0">
          <Field label="Name" value={dx.patient_name} />
          <Field label="Email" value={dx.patient_email} />
          <Field label="Patient ID" value={<span className="font-mono text-xs">{dx.patient_id}</span>} />
        </Card>
      </Section>

      {/* Scan metadata */}
      <Section title="Scan">
        <Card className="divide-y divide-gray-50 py-0">
          <Field label="Modality" value={dx.modality?.replace(/_/g, " ")} />
          <Field label="Model used" value={dx.model_used} />
          <Field
            label="Confidence"
            value={dx.confidence_score != null ? `${(dx.confidence_score * 100).toFixed(1)}%` : null}
          />
          <Field
            label="Urgency"
            value={
              dx.urgency ? (
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${URGENCY_COLORS[dx.urgency] ?? "bg-gray-100 text-gray-800"}`}>
                  {dx.urgency}
                </span>
              ) : null
            }
          />
          <Field label="Images" value={`${dx.image_keys.length} file${dx.image_keys.length !== 1 ? "s" : ""}`} />
          <Field label="Submitted" value={fmt(dx.created_at)} />
          <Field label="Last updated" value={fmt(dx.updated_at)} />
          <Field label="Doctor reviewed" value={dx.doctor_reviewed_at ? fmt(dx.doctor_reviewed_at) : "Not yet reviewed"} />
        </Card>
      </Section>

      {/* AI Report */}
      {dx.report && !dx.report.error && (
        <Section title="AI Report">
          <Card className="space-y-5">
            {dx.report.summary && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Summary</p>
                <p className="text-sm text-gray-800 leading-relaxed">{dx.report.summary}</p>
              </div>
            )}
            {dx.report.impression && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Impression</p>
                <p className="text-sm text-gray-800 leading-relaxed">{dx.report.impression}</p>
              </div>
            )}
            {dx.report.findings && dx.report.findings.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Findings</p>
                <ul className="space-y-1">
                  {dx.report.findings.map((f, i) => (
                    <li key={i} className="text-sm text-gray-700 flex gap-2">
                      <span className="text-gray-300 mt-0.5">•</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {dx.report.differential_diagnoses && dx.report.differential_diagnoses.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Differential diagnoses
                </p>
                <div className="flex flex-wrap gap-2">
                  {dx.report.differential_diagnoses.map((d, i) => (
                    <span key={i} className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-700">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {dx.report.recommendations && dx.report.recommendations.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Recommendations</p>
                <ul className="space-y-1">
                  {dx.report.recommendations.map((r, i) => (
                    <li key={i} className="text-sm text-gray-700 flex gap-2">
                      <span className="text-primary-400 mt-0.5">→</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {dx.report.patient_notes && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Patient notes</p>
                <p className="text-sm text-gray-700 italic">{dx.report.patient_notes}</p>
              </div>
            )}
          </Card>
        </Section>
      )}

      {dx.report?.error && (
        <Section title="AI Report">
          <Card className="border-red-100 bg-red-50">
            <p className="text-sm text-red-700 font-medium">Processing error</p>
            <p className="text-sm text-red-600 mt-1">{dx.report.error}</p>
          </Card>
        </Section>
      )}

      {/* Doctor notes */}
      {dx.doctor_notes && (
        <Section title="Doctor notes">
          <Card>
            <p className="text-sm text-gray-800 leading-relaxed">{dx.doctor_notes}</p>
          </Card>
        </Section>
      )}
    </div>
  );
}
