"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { adminBanUser, adminDeleteUser, adminListUsers, adminUnbanUser } from "@/lib/api";
import type { AdminUser } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatDate } from "@/lib/utils";

const ROLES = ["", "patient", "doctor", "admin"];

function roleBadge(role: string) {
  const map: Record<string, string> = {
    patient: "bg-blue-100 text-blue-800",
    doctor: "bg-purple-100 text-purple-800",
    admin: "bg-red-100 text-red-800",
  };
  return map[role] ?? "bg-gray-100 text-gray-800";
}

function UserRow({
  u,
  onBan,
  onUnban,
  onDelete,
}: {
  u: AdminUser;
  onBan: (id: string) => void;
  onUnban: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [confirmBan, setConfirmBan] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (u.role === "admin") {
    return (
      <tr className="hover:bg-gray-50">
        <td className="px-6 py-3">
          <Link href={`/admin/users/${u.id}`} className="text-primary-600 hover:underline font-medium">
            {u.display_name ?? u.email}
          </Link>
          {u.display_name && <p className="text-xs text-gray-400">{u.email}</p>}
        </td>
        <td className="px-6 py-3"><Badge className={roleBadge(u.role)}>{u.role}</Badge></td>
        <td className="px-6 py-3">
          <span className={`inline-block h-2 w-2 rounded-full ${u.is_active ? "bg-green-500" : "bg-gray-300"}`} />
          <span className="ml-2 text-sm text-gray-600">{u.is_active ? "Active" : "Inactive"}</span>
        </td>
        <td className="px-6 py-3">
          {u.is_verified ? <span className="text-green-600 text-sm">Verified</span> : <span className="text-gray-400 text-sm">Unverified</span>}
        </td>
        <td className="px-6 py-3 text-gray-400 text-sm">{formatDate(u.created_at)}</td>
        <td className="px-6 py-3" />
      </tr>
    );
  }

  return (
    <>
      <tr className="hover:bg-gray-50">
        <td className="px-6 py-3">
          <Link href={`/admin/users/${u.id}`} className="text-primary-600 hover:underline font-medium">
            {u.display_name ?? u.email}
          </Link>
          {u.display_name && <p className="text-xs text-gray-400">{u.email}</p>}
        </td>
        <td className="px-6 py-3"><Badge className={roleBadge(u.role)}>{u.role}</Badge></td>
        <td className="px-6 py-3">
          <span className={`inline-block h-2 w-2 rounded-full ${u.is_active ? "bg-green-500" : "bg-gray-300"}`} />
          <span className="ml-2 text-sm text-gray-600">{u.is_active ? "Active" : "Banned"}</span>
        </td>
        <td className="px-6 py-3">
          {u.is_verified ? <span className="text-green-600 text-sm">Verified</span> : <span className="text-gray-400 text-sm">Unverified</span>}
        </td>
        <td className="px-6 py-3 text-gray-400 text-sm">{formatDate(u.created_at)}</td>
        <td className="px-6 py-3">
          <div className="flex justify-end gap-3">
            {u.is_active ? (
              <button
                onClick={() => setConfirmBan(true)}
                className="text-xs text-orange-600 hover:underline"
              >
                Ban
              </button>
            ) : (
              <button
                onClick={() => onUnban(u.id)}
                className="text-xs text-green-600 hover:underline"
              >
                Unban
              </button>
            )}
            <button
              onClick={() => setConfirmDelete(true)}
              className="text-xs text-red-600 hover:underline"
            >
              Delete
            </button>
          </div>
        </td>
      </tr>

      <ConfirmDialog
        open={confirmBan}
        title={`Ban ${u.display_name ?? u.email}?`}
        description="This will immediately revoke their access to the platform. You can unban them later."
        confirmLabel="Ban user"
        destructive
        onConfirm={() => { setConfirmBan(false); onBan(u.id); }}
        onCancel={() => setConfirmBan(false)}
      />
      <ConfirmDialog
        open={confirmDelete}
        title={`Permanently delete ${u.display_name ?? u.email}?`}
        description="This will permanently remove the user account. Medical records are retained. This cannot be undone."
        confirmLabel="Delete permanently"
        destructive
        onConfirm={() => { setConfirmDelete(false); onDelete(u.id); }}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}

export default function AdminUsersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page, role, search],
    queryFn: () => adminListUsers({ page, role: role || undefined, search: search || undefined }),
  });

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["admin-users"] });
  }

  const { mutate: ban } = useMutation({ mutationFn: adminBanUser, onSuccess: invalidate });
  const { mutate: unban } = useMutation({ mutationFn: adminUnbanUser, onSuccess: invalidate });
  const { mutate: del } = useMutation({ mutationFn: adminDeleteUser, onSuccess: invalidate });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Users</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search by email…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="h-9 rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 w-64"
        />
        <select
          value={role}
          onChange={(e) => { setRole(e.target.value); setPage(1); }}
          className="h-9 rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-500 focus:outline-none"
        >
          <option value="">All roles</option>
          {ROLES.filter(Boolean).map((r) => (
            <option key={r} value={r} className="capitalize">{r}</option>
          ))}
        </select>
        {data && (
          <span className="self-center text-sm text-gray-400">{data.total} users</span>
        )}
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
                <th className="text-left font-medium text-gray-500 px-6 py-3">User</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Role</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Status</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Verified</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Joined</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(data?.users ?? []).map((u) => (
                <UserRow
                  key={u.id}
                  u={u}
                  onBan={(id) => ban(id)}
                  onUnban={(id) => unban(id)}
                  onDelete={(id) => del(id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            ← Prev
          </button>
          <span className="self-center text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
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
