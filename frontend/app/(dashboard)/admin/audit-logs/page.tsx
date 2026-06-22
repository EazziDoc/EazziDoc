"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminGetAuditLogs } from "@/lib/api";
import { Card } from "@/components/ui/card";

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  "user.activated": { label: "Activated", color: "text-green-700 bg-green-50" },
  "user.deactivated": { label: "Deactivated", color: "text-red-700 bg-red-50" },
  "doctor.verified": { label: "Doctor verified", color: "text-blue-700 bg-blue-50" },
  "doctor.unverified": { label: "Verification revoked", color: "text-orange-700 bg-orange-50" },
  "user.role_changed": { label: "Role changed", color: "text-purple-700 bg-purple-50" },
  "user.updated": { label: "User updated", color: "text-gray-700 bg-gray-100" },
  "diagnosis.requeued": { label: "Requeued", color: "text-yellow-700 bg-yellow-50" },
};

function ActionBadge({ action }: { action: string }) {
  const cfg = ACTION_LABELS[action] ?? { label: action, color: "text-gray-700 bg-gray-100" };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const ACTION_FILTERS = ["", ...Object.keys(ACTION_LABELS)];

export default function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-audit-logs", page, actionFilter],
    queryFn: () => adminGetAuditLogs({ page, page_size: 50, action: actionFilter || undefined }),
  });

  const totalPages = data ? Math.ceil(data.total / 50) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit logs</h1>
          <p className="text-sm text-gray-500 mt-0.5">All admin actions across the platform</p>
        </div>
        {data && (
          <span className="text-sm text-gray-400">{data.total} total entries</span>
        )}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-600">Filter by action</label>
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option value="">All actions</option>
          {Object.entries(ACTION_LABELS).map(([key, { label }]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      <Card className="p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
          </div>
        ) : !data?.entries.length ? (
          <p className="text-center text-gray-400 py-16">No audit log entries found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Timestamp</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Action</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Actor</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Target</th>
                  <th className="text-left font-medium text-gray-500 px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmt(entry.created_at)}</td>
                    <td className="px-4 py-3"><ActionBadge action={entry.action} /></td>
                    <td className="px-4 py-3 text-gray-700 max-w-[200px] truncate">{entry.actor_email}</td>
                    <td className="px-4 py-3">
                      <span className="text-gray-500 capitalize">{entry.target_type}</span>
                      <span className="text-gray-300 mx-1">·</span>
                      <span className="text-gray-400 font-mono text-xs">{entry.target_id.slice(0, 8)}…</span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs max-w-[200px] truncate">
                      {entry.meta ? JSON.stringify(entry.meta) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Pagination */}
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
