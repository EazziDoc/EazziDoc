"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import {
  adminGetUser,
  adminRejectPatientIdentity,
  adminUpdateUser,
  adminVerifyPatientIdentity,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatDateTime } from "@/lib/utils";

function roleBadge(role: string) {
  const map: Record<string, string> = {
    patient: "bg-blue-100 text-blue-800",
    doctor: "bg-purple-100 text-purple-800",
    admin: "bg-red-100 text-red-800",
  };
  return map[role] ?? "bg-gray-100 text-gray-800";
}

function idStatusBadge(status: string | null | undefined) {
  if (!status) return null;
  const map: Record<string, string> = {
    unverified: "bg-gray-100 text-gray-600",
    pending_review: "bg-blue-100 text-blue-700",
    verified: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
  };
  const label: Record<string, string> = {
    unverified: "Unverified",
    pending_review: "Pending review",
    verified: "Verified",
    rejected: "Rejected",
  };
  return (
    <Badge className={map[status] ?? "bg-gray-100 text-gray-600"}>
      {label[status] ?? status}
    </Badge>
  );
}

function formatIdType(raw: string | null | undefined) {
  if (!raw) return "—";
  return (
    { national_id: "National ID", passport: "Passport", drivers_license: "Driver's license" }[
      raw
    ] ?? raw
  );
}

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const [confirmVerify, setConfirmVerify] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const rejectDialogRef = useRef<HTMLDialogElement>(null);

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

  const { mutate: verifyId, isPending: verifyPending } = useMutation({
    mutationFn: () => adminVerifyPatientIdentity(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-user", id] });
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const { mutate: rejectId, isPending: rejectPending } = useMutation({
    mutationFn: (reason: string) => adminRejectPatientIdentity(id, reason),
    onSuccess: () => {
      setRejectReason("");
      rejectDialogRef.current?.close();
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

  const idStatus = user.identity_verification_status;
  const isPendingReview = idStatus === "pending_review";

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

      {/* Identity verification card (patients only) */}
      {user.role === "patient" && (
        <Card className="space-y-4">
          <CardHeader>
            <CardTitle>Identity verification</CardTitle>
          </CardHeader>

          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">Status</dt>
              <dd className="mt-1">{idStatusBadge(idStatus) ?? <span className="text-gray-400">—</span>}</dd>
            </div>
            <div>
              <dt className="text-gray-500">ID type</dt>
              <dd className="mt-1 text-gray-700">{formatIdType(user.id_type)}</dd>
            </div>
            <div>
              <dt className="text-gray-500">ID number</dt>
              <dd className="mt-1 text-gray-700">{user.id_number ?? "—"}</dd>
            </div>
            {user.id_verified_at && (
              <div>
                <dt className="text-gray-500">Verified at</dt>
                <dd className="mt-1 text-gray-700">{formatDateTime(user.id_verified_at)}</dd>
              </div>
            )}
            {user.id_rejection_reason && (
              <div className="col-span-2">
                <dt className="text-gray-500">Rejection reason</dt>
                <dd className="mt-1 text-red-600">{user.id_rejection_reason}</dd>
              </div>
            )}
            {user.id_document_url && (
              <div className="col-span-2">
                <dt className="text-gray-500">Document</dt>
                <dd className="mt-1">
                  <a
                    href={user.id_document_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-600 hover:underline text-sm"
                  >
                    View / download document ↗
                  </a>
                </dd>
              </div>
            )}
          </dl>

          {isPendingReview && (
            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setConfirmVerify(true)}
                disabled={verifyPending || rejectPending}
                className="rounded-lg bg-green-50 text-green-700 hover:bg-green-100 px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
              >
                Approve identity
              </button>
              <button
                onClick={() => {
                  setShowRejectDialog(true);
                  setTimeout(() => rejectDialogRef.current?.showModal(), 0);
                }}
                disabled={verifyPending || rejectPending}
                className="rounded-lg bg-red-50 text-red-600 hover:bg-red-100 px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
              >
                Reject identity
              </button>
            </div>
          )}
        </Card>
      )}

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

      {/* Approve identity confirm dialog */}
      <ConfirmDialog
        open={confirmVerify}
        title="Approve identity"
        description="This will mark the patient as identity-verified and set their account as verified. This action cannot be undone without manual intervention."
        confirmLabel="Approve"
        onConfirm={() => {
          setConfirmVerify(false);
          verifyId();
        }}
        onCancel={() => setConfirmVerify(false)}
      />

      {/* Reject identity dialog */}
      {showRejectDialog && (
        <dialog
          ref={rejectDialogRef}
          className="rounded-xl p-6 shadow-xl w-full max-w-md backdrop:bg-black/40"
          onClose={() => setShowRejectDialog(false)}
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Reject identity</h2>
          <p className="text-sm text-gray-500 mb-4">
            Provide a reason — the patient will see this message and can resubmit.
          </p>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            placeholder="e.g. Document is blurry or ID number doesn't match."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <div className="flex justify-end gap-3 mt-4">
            <button
              onClick={() => {
                rejectDialogRef.current?.close();
                setShowRejectDialog(false);
              }}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              onClick={() => rejectId(rejectReason)}
              disabled={rejectReason.trim().length < 5 || rejectPending}
              className="rounded-lg bg-red-600 text-white hover:bg-red-700 px-4 py-2 text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {rejectPending ? "Rejecting…" : "Reject"}
            </button>
          </div>
        </dialog>
      )}
    </div>
  );
}
