"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { adminGetDoctor, adminApproveDoctor, adminRejectDoctor } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const STATUS_COLORS: Record<string, string> = {
  pending_review: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

const STATUS_LABELS: Record<string, string> = {
  pending_review: "Pending review",
  approved: "Approved",
  rejected: "Rejected",
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start gap-4 py-2 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500 shrink-0">{label}</span>
      <span className="text-sm text-gray-900 text-right">{value ?? "—"}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{title}</h2>
      {children}
    </section>
  );
}

function PrintButton() {
  return (
    <button
      onClick={() => window.print()}
      className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors print:hidden"
    >
      Export PDF / Print
    </button>
  );
}

export default function AdminDoctorDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  const { data: doc, isLoading } = useQuery({
    queryKey: ["admin-doctor", id],
    queryFn: () => adminGetDoctor(id),
  });

  const approve = useMutation({
    mutationFn: () => adminApproveDoctor(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-doctor", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
    },
  });

  const reject = useMutation({
    mutationFn: () => adminRejectDoctor(id, rejectReason),
    onSuccess: () => {
      setShowRejectForm(false);
      queryClient.invalidateQueries({ queryKey: ["admin-doctor", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="text-center py-16 text-gray-400">
        Doctor not found.{" "}
        <Link href="/admin/doctors" className="text-primary-600 hover:underline">Back</Link>
      </div>
    );
  }

  const isPending = doc.registration_status === "pending_review";

  return (
    <>
      {/* Print-only header */}
      <div className="hidden print:block mb-6">
        <h1 className="text-xl font-bold">EazziDoc — Doctor Registration</h1>
        <p className="text-sm text-gray-500">Printed: {new Date().toLocaleString()}</p>
      </div>

      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 print:hidden">
          <div className="space-y-1">
            <Link href="/admin/doctors" className="text-sm text-gray-400 hover:text-gray-600">
              ← Doctor registrations
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">
              Dr. {doc.first_name} {doc.last_name}
            </h1>
            <p className="text-xs font-mono text-gray-400">{doc.id}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold capitalize ${STATUS_COLORS[doc.registration_status] ?? "bg-gray-100 text-gray-800"}`}>
              {STATUS_LABELS[doc.registration_status]}
            </span>
            <PrintButton />
          </div>
        </div>

        {/* Rejection reason if rejected */}
        {doc.registration_status === "rejected" && doc.rejection_reason && (
          <Card className="border-red-100 bg-red-50">
            <p className="text-sm font-semibold text-red-700">Rejection reason</p>
            <p className="text-sm text-red-600 mt-1">{doc.rejection_reason}</p>
          </Card>
        )}

        {/* Personal info */}
        <Section title="Doctor information">
          <Card className="divide-y divide-gray-50 py-0">
            <Field label="Full name" value={`${doc.first_name} ${doc.last_name}`} />
            <Field label="Email" value={doc.email} />
            <Field label="Specialty" value={doc.specialty} />
            <Field label="Licence / registration no." value={doc.license_number} />
            <Field label="Submitted" value={fmt(doc.created_at)} />
            {doc.reviewed_at && <Field label="Reviewed at" value={fmt(doc.reviewed_at)} />}
          </Card>
        </Section>

        {/* Qualifications */}
        <Section title="Qualifications & certifications">
          <Card>
            {doc.qualifications.length > 0 ? (
              <ul className="space-y-1.5">
                {doc.qualifications.map((q) => (
                  <li key={q} className="flex items-start gap-2 text-sm text-gray-800">
                    <span className="text-primary-500 mt-0.5 shrink-0">✓</span>
                    {q}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-400">No standard qualifications listed.</p>
            )}
            {doc.other_qualifications && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Other qualifications</p>
                <p className="text-sm text-gray-700">{doc.other_qualifications}</p>
              </div>
            )}
          </Card>
        </Section>

        {/* Certification documents */}
        {doc.certification_urls.length > 0 && (
          <Section title="Uploaded certification documents">
            <Card>
              <ul className="space-y-2">
                {doc.certification_urls.map((url, i) => (
                  <li key={i}>
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm text-primary-600 hover:underline"
                    >
                      <span className="text-gray-400">📄</span>
                      Document {i + 1}
                    </a>
                  </li>
                ))}
              </ul>
            </Card>
          </Section>
        )}

        {/* Admin actions */}
        {isPending && (
          <Section title="Review decision">
            <Card className="space-y-4 print:hidden">
              <p className="text-sm text-gray-600">
                Once approved, the doctor will be visible to patients for appointment booking.
                Rejected doctors must resubmit their registration.
              </p>

              {!showRejectForm ? (
                <div className="flex gap-3">
                  <Button
                    onClick={() => approve.mutate()}
                    loading={approve.isPending}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    Approve registration
                  </Button>
                  <button
                    onClick={() => setShowRejectForm(true)}
                    className="rounded-xl border border-red-300 px-5 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors"
                  >
                    Reject
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <label className="text-sm font-medium text-gray-700">
                    Rejection reason <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    rows={3}
                    placeholder="Explain why the registration is being rejected (this will be shown to the doctor)…"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100 resize-none"
                  />
                  {reject.error && (
                    <p className="text-sm text-red-600">{(reject.error as Error).message}</p>
                  )}
                  <div className="flex gap-3">
                    <Button
                      onClick={() => reject.mutate()}
                      loading={reject.isPending}
                      disabled={!rejectReason.trim()}
                      className="bg-red-600 hover:bg-red-700"
                    >
                      Confirm rejection
                    </Button>
                    <button
                      onClick={() => { setShowRejectForm(false); setRejectReason(""); }}
                      className="text-sm text-gray-500 hover:text-gray-700"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </Card>
          </Section>
        )}
      </div>

      {/* Print-only footer */}
      <div className="hidden print:block mt-8 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">EazziDoc — Confidential registration review document</p>
      </div>
    </>
  );
}
