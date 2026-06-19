"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminListDiagnoses, adminRequeueDiagnosis } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, statusColor } from "@/lib/utils";

const STATUSES = ["", "pending", "processing", "ai_complete", "under_review", "confirmed", "overridden", "flagged", "failed"];
const MODALITIES = ["", "chest_xray", "fundus", "skin", "brain_mri", "mammography"];
const URGENCIES = ["", "routine", "urgent", "emergent"];

const urgencyColor: Record<string, string> = {
  routine: "bg-green-100 text-green-800",
  urgent: "bg-orange-100 text-orange-800",
  emergent: "bg-red-100 text-red-800",
};

export default function AdminDiagnosesPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [modality, setModality] = useState("");
  const [urgency, setUrgency] = useState("");
  const [page, setPage] = useState(1);
  const [requeued, setRequeued] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ["admin-diagnoses", page, status, modality, urgency],
    queryFn: () =>
      adminListDiagnoses({
        page,
        status: status || undefined,
        modality: modality || undefined,
        urgency: urgency || undefined,
      }),
  });

  const { mutate: requeue } = useMutation({
    mutationFn: adminRequeueDiagnosis,
    onSuccess: (_, id) => {
      setRequeued((prev) => new Set(prev).add(id));
      qc.invalidateQueries({ queryKey: ["admin-diagnoses"] });
    },
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Diagnoses</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        {[
          { value: status, onChange: (v: string) => { setStatus(v); setPage(1); }, options: STATUSES, placeholder: "All statuses" },
          { value: modality, onChange: (v: string) => { setModality(v); setPage(1); }, options: MODALITIES, placeholder: "All modalities" },
          { value: urgency, onChange: (v: string) => { setUrgency(v); setPage(1); }, options: URGENCIES, placeholder: "All urgencies" },
        ].map((f, i) => (
          <select
            key={i}
            value={f.value}
            onChange={(e) => f.onChange(e.target.value)}
            className="h-9 rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-500 focus:outline-none capitalize"
          >
            <option value="">{f.placeholder}</option>
            {f.options.filter(Boolean).map((o) => (
              <option key={o} value={o} className="capitalize">{o.replace(/_/g, " ")}</option>
            ))}
          </select>
        ))}
        {data && <span className="self-center text-sm text-gray-400">{data.total} diagnoses</span>}
      </div>

      <Card className="p-0">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left font-medium text-gray-500 px-6 py-3">Patient</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Modality</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Status</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Urgency</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Confidence</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Date</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(data?.diagnoses ?? []).map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 text-gray-700">{d.patient_name ?? "—"}</td>
                  <td className="px-6 py-3 capitalize text-gray-700">
                    {d.modality?.replace(/_/g, " ") ?? "—"}
                  </td>
                  <td className="px-6 py-3">
                    <Badge className={statusColor(d.status)}>{d.status.replace(/_/g, " ")}</Badge>
                  </td>
                  <td className="px-6 py-3">
                    {d.urgency ? (
                      <Badge className={urgencyColor[d.urgency] ?? ""}>{d.urgency}</Badge>
                    ) : "—"}
                  </td>
                  <td className="px-6 py-3 text-gray-600">
                    {d.confidence_score != null
                      ? `${Math.round(d.confidence_score * 100)}%`
                      : "—"}
                  </td>
                  <td className="px-6 py-3 text-gray-400">{formatDate(d.created_at)}</td>
                  <td className="px-6 py-3 text-right">
                    {(d.status === "failed" || d.status === "pending") && (
                      <button
                        onClick={() => requeue(d.id)}
                        disabled={requeued.has(d.id)}
                        className="text-xs text-primary-600 hover:underline disabled:text-gray-400"
                      >
                        {requeued.has(d.id) ? "Queued" : "Re-queue"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            ← Prev
          </button>
          <span className="self-center text-sm text-gray-500">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
