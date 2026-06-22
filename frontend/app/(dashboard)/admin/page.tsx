"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  adminGetAppointmentStats,
  adminGetDiagnosisStats,
  adminGetOverview,
} from "@/lib/api";
import { Card } from "@/components/ui/card";

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent?: string;
}) {
  return (
    <Card className="space-y-1">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold ${accent ?? "text-gray-900"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </Card>
  );
}

function pct(n: number | null | undefined) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function secs(n: number | null | undefined) {
  if (n == null) return "—";
  if (n < 60) return `${Math.round(n)}s`;
  if (n < 3600) return `${Math.round(n / 60)}m`;
  return `${(n / 3600).toFixed(1)}h`;
}

export default function AdminOverviewPage() {
  const { data: ov } = useQuery({ queryKey: ["admin-overview"], queryFn: adminGetOverview });
  const { data: dx } = useQuery({
    queryKey: ["admin-dx-stats"],
    queryFn: adminGetDiagnosisStats,
  });
  const { data: appt } = useQuery({
    queryKey: ["admin-appt-stats"],
    queryFn: adminGetAppointmentStats,
  });

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Admin overview</h1>
        <span className="text-xs text-gray-400">Live data</span>
      </div>

      {/* Platform KPIs */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Platform</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KpiCard label="Total users" value={ov?.total_users ?? "—"} sub={`+${ov?.new_users_30d ?? 0} this month`} />
          <KpiCard label="Patients" value={ov?.total_patients ?? "—"} />
          <KpiCard label="Doctors" value={ov?.total_doctors ?? "—"} sub={`${ov?.verified_doctors ?? 0} verified`} />
          <KpiCard label="Appointments" value={ov?.total_appointments ?? "—"} />
        </div>
      </section>

      {/* Diagnosis KPIs */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Diagnoses</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KpiCard label="Total" value={ov?.total_diagnoses ?? "—"} sub={`+${ov?.new_diagnoses_30d ?? 0} this month`} />
          <KpiCard label="Pending" value={ov?.pending_diagnoses ?? "—"} accent={ov?.pending_diagnoses ? "text-yellow-600" : undefined} />
          <KpiCard label="Awaiting review" value={ov?.ai_complete_diagnoses ?? "—"} accent={ov?.ai_complete_diagnoses ? "text-blue-600" : undefined} />
          <KpiCard label="Failed" value={ov?.failed_diagnoses ?? "—"} accent={ov?.failed_diagnoses ? "text-red-600" : undefined} />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KpiCard label="Avg confidence" value={dx?.avg_confidence != null ? `${(dx.avg_confidence * 100).toFixed(0)}%` : "—"} />
          <KpiCard label="Override rate" value={pct(dx?.override_rate)} sub="AI reports overridden by doctors" />
          <KpiCard label="Avg time to review" value={secs(dx?.avg_time_to_review_secs)} />
          <KpiCard label="Groq fallback use" value={dx?.by_model.find((m) => m.model_used?.includes("groq"))?.count ?? 0} sub="times Groq was used instead of Gemini" />
        </div>
      </section>

      {/* Modality breakdown */}
      {dx && dx.by_modality.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Diagnoses by modality</h2>
          <Card className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left font-medium text-gray-500 px-6 py-3">Modality</th>
                  <th className="text-right font-medium text-gray-500 px-6 py-3">Count</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {dx.by_modality.map((m) => (
                  <tr key={m.modality}>
                    <td className="px-6 py-3 capitalize text-gray-700">{m.modality.replace(/_/g, " ")}</td>
                    <td className="px-6 py-3 text-right font-medium text-gray-900">{m.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      )}

      {/* Appointment funnel */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Appointment funnel</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KpiCard label="Booked" value={appt?.booked ?? "—"} />
          <KpiCard label="Confirmed" value={appt?.confirmed ?? "—"} />
          <KpiCard label="Completed" value={appt?.completed ?? "—"} />
          <KpiCard label="Cancelled" value={appt?.cancelled ?? "—"} />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <KpiCard label="Completion rate" value={pct(appt?.completion_rate)} />
          <KpiCard label="Cancellation rate" value={pct(appt?.cancellation_rate)} />
          <KpiCard label="Avg duration" value={appt?.avg_duration_mins != null ? `${Math.round(appt.avg_duration_mins)} min` : "—"} />
        </div>
      </section>

      {/* Quick links */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Quick actions</h2>
        <div className="flex flex-wrap gap-3">
          {[
            { href: "/admin/users", label: "Manage users" },
            { href: "/admin/diagnoses", label: "Browse diagnoses" },
            { href: "/admin/queue", label: "Queue health" },
            { href: "/admin/audit-logs", label: "Audit logs" },
          ].map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {l.label} →
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
