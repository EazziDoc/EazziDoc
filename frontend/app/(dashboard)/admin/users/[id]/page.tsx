"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { adminGetUser, adminUpdateUser } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";

function roleBadge(role: string) {
  const map: Record<string, string> = {
    patient: "bg-blue-100 text-blue-800",
    doctor: "bg-purple-100 text-purple-800",
    admin: "bg-red-100 text-red-800",
  };
  return map[role] ?? "bg-gray-100 text-gray-800";
}

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: user, isLoading } = useQuery({
    queryKey: ["admin-user", id],
    queryFn: () => adminGetUser(id),
  });

  const { mutate: update, isPending } = useMutation({
    mutationFn: (data: { is_active?: boolean; is_verified?: boolean }) =>
      adminUpdateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-user", id] });
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="text-center py-24 text-gray-400">
        User not found.{" "}
        <Link href="/admin/users" className="text-primary-600 hover:underline">
          Back
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-start gap-3">
        <Link href="/admin/users" className="text-sm text-gray-400 hover:text-gray-600 mt-1">
          ←
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {user.display_name ?? user.email}
          </h1>
          {user.display_name && (
            <p className="text-gray-400 text-sm mt-0.5">{user.email}</p>
          )}
        </div>
      </div>

      {/* Overview card */}
      <Card className="space-y-4">
        <CardHeader>
          <CardTitle>Account details</CardTitle>
        </CardHeader>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Role</dt>
            <dd className="mt-1">
              <Badge className={roleBadge(user.role)}>{user.role}</Badge>
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Status</dt>
            <dd className="mt-1 font-medium">
              <span className={user.is_active ? "text-green-600" : "text-gray-400"}>
                {user.is_active ? "Active" : "Inactive"}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Verified</dt>
            <dd className="mt-1 font-medium">
              <span className={user.is_verified ? "text-green-600" : "text-gray-400"}>
                {user.is_verified ? "Yes" : "No"}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Joined</dt>
            <dd className="mt-1 text-gray-700">{formatDateTime(user.created_at)}</dd>
          </div>
          {user.specialty && (
            <div>
              <dt className="text-gray-500">Specialty</dt>
              <dd className="mt-1 text-gray-700">{user.specialty}</dd>
            </div>
          )}
          {user.total_diagnoses !== undefined && (
            <div>
              <dt className="text-gray-500">Total diagnoses</dt>
              <dd className="mt-1 font-semibold text-gray-900">{user.total_diagnoses}</dd>
            </div>
          )}
          {user.total_appointments !== undefined && (
            <div>
              <dt className="text-gray-500">Total appointments</dt>
              <dd className="mt-1 font-semibold text-gray-900">{user.total_appointments}</dd>
            </div>
          )}
        </dl>
      </Card>

      {/* Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Admin actions</CardTitle>
        </CardHeader>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => update({ is_active: !user.is_active })}
            disabled={isPending}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              user.is_active
                ? "bg-red-50 text-red-600 hover:bg-red-100"
                : "bg-green-50 text-green-700 hover:bg-green-100"
            }`}
          >
            {user.is_active ? "Deactivate account" : "Reactivate account"}
          </button>

          {user.role === "doctor" && !user.is_verified && (
            <button
              onClick={() => update({ is_verified: true })}
              disabled={isPending}
              className="rounded-lg bg-primary-50 text-primary-700 hover:bg-primary-100 px-4 py-2 text-sm font-medium transition-colors"
            >
              Verify doctor
            </button>
          )}

          {user.role === "doctor" && user.is_verified && (
            <button
              onClick={() => update({ is_verified: false })}
              disabled={isPending}
              className="rounded-lg bg-orange-50 text-orange-700 hover:bg-orange-100 px-4 py-2 text-sm font-medium transition-colors"
            >
              Revoke verification
            </button>
          )}
        </div>
      </Card>
    </div>
  );
}
