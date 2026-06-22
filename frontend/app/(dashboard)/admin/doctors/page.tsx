"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { adminListDoctors } from "@/lib/api";
import type { AdminDoctorItem } from "@/lib/api";
import { Card } from "@/components/ui/card";

const STATUS_BADGES: Record<string, string> = {
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
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export default function AdminDoctorsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("pending_review");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-doctors", page, statusFilter],
    queryFn: () => adminListDoctors({ page, status: statusFilter || undefined }),
  });

  const totalPages = data ? Math.ceil(data.total / 25) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Doctor registrations</h1>
          <p className="text-sm text-gray-500 mt-0.5">Review, approve, or reject doctor applications</p>
        </div>
        {data && <span className="text-sm text-gray-400">{data.total} total</span>}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-600">Status</label>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option value="">All</option>
          <option value="pending_review">Pending review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <Card className="p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
          </div>
        ) : !data?.doctors.length ? (
          <p className="text-center text-gray-400 py-16">No doctor registrations found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Doctor</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Specialty</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Qualifications</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Status</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Submitted</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.doctors.map((doc: AdminDoctorItem) => (
                  <tr key={doc.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{doc.first_name} {doc.last_name}</div>
                      <div className="text-xs text-gray-400">{doc.email}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{doc.specialty ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className="text-gray-600">{doc.qualifications.length}</span>
                      <span className="text-gray-400"> cert{doc.qualifications.length !== 1 ? "s" : ""}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGES[doc.registration_status] ?? "bg-gray-100 text-gray-700"}`}>
                        {STATUS_LABELS[doc.registration_status] ?? doc.registration_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmt(doc.created_at)}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/admin/doctors/${doc.id}`}
                        className="text-primary-600 hover:underline text-sm font-medium"
                      >
                        Review →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-40 hover:bg-gray-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-40 hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
