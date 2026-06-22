"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Calendar, CheckCircle, Clock, FileText, Upload } from "lucide-react";
import Link from "next/link";
import { getPatientProfile, listAppointments, listDiagnoses } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, statusColor } from "@/lib/utils";

export default function PatientDashboard() {
  const { user } = useAuth();
  const { data: diagnoses = [] } = useQuery({
    queryKey: ["diagnoses"],
    queryFn: listDiagnoses,
  });
  const { data: appointments = [] } = useQuery({
    queryKey: ["appointments"],
    queryFn: listAppointments,
  });
  const { data: profile } = useQuery({
    queryKey: ["patient-profile"],
    queryFn: getPatientProfile,
  });

  const idStatus = profile?.identity_verification_status ?? "unverified";

  const pending = diagnoses.filter((d) => d.status === "pending").length;
  const ready = diagnoses.filter((d) => d.status === "ai_complete").length;
  const upcoming = appointments.filter((a) =>
    ["booked", "confirmed"].includes(a.status),
  ).length;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {user?.first_name}
        </h1>
      </div>

      {/* Identity verification banner */}
      {idStatus === "unverified" && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-800">Verify your identity</p>
            <p className="text-sm text-amber-700 mt-0.5">
              Submit a government-issued ID to unlock full platform access.
            </p>
          </div>
          <Link
            href="/patient/settings#identity-verification"
            className="shrink-0 text-sm font-medium text-amber-800 underline hover:text-amber-900"
          >
            Complete →
          </Link>
        </div>
      )}
      {idStatus === "pending_review" && (
        <div className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
          <Clock className="h-5 w-5 text-blue-500 shrink-0" />
          <p className="text-sm text-blue-800">
            Your identity verification is <strong>under review</strong>. We'll notify you once it's approved.
          </p>
        </div>
      )}
      {idStatus === "rejected" && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">Identity verification rejected</p>
            {profile?.id_rejection_reason && (
              <p className="text-sm text-red-700 mt-0.5">{profile.id_rejection_reason}</p>
            )}
          </div>
          <Link
            href="/patient/settings#identity-verification"
            className="shrink-0 text-sm font-medium text-red-800 underline hover:text-red-900"
          >
            Resubmit →
          </Link>
        </div>
      )}
      {idStatus === "verified" && (
        <div className="flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3">
          <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
          <p className="text-sm text-green-800">Identity verified.</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Pending analysis", value: pending, icon: Upload, color: "text-yellow-600 bg-yellow-50" },
          { label: "Reports ready", value: ready, icon: FileText, color: "text-blue-600 bg-blue-50" },
          { label: "Upcoming appointments", value: upcoming, icon: Calendar, color: "text-green-600 bg-green-50" },
        ].map((s) => (
          <Card key={s.label} className="flex items-center gap-4">
            <div className={`rounded-lg p-3 ${s.color}`}>
              <s.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{s.value}</p>
              <p className="text-sm text-gray-500">{s.label}</p>
            </div>
          </Card>
        ))}
      </div>

      {/* Quick actions */}
      <Card>
        <h2 className="font-semibold text-gray-900 mb-4">Quick actions</h2>
        <div className="flex gap-3">
          <Link
            href="/patient/upload"
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Upload className="h-4 w-4" /> New diagnosis
          </Link>
          <Link
            href="/patient/appointments"
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Calendar className="h-4 w-4" /> Book appointment
          </Link>
        </div>
      </Card>

      {/* Recent diagnoses */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Recent diagnoses</h2>
          <Link href="/patient/diagnoses" className="text-sm text-primary-600 hover:underline">
            View all
          </Link>
        </div>
        {diagnoses.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">
            No diagnoses yet.{" "}
            <Link href="/patient/upload" className="text-primary-600 hover:underline">
              Upload your first image
            </Link>
          </p>
        ) : (
          <div className="divide-y divide-gray-100">
            {diagnoses.slice(0, 5).map((d) => (
              <Link
                key={d.id}
                href={`/patient/diagnoses/${d.id}`}
                className="flex items-center justify-between py-3 hover:bg-gray-50 rounded-lg px-2 -mx-2 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {d.modality?.replace("_", " ") ?? "Analysing…"}
                  </p>
                  <p className="text-xs text-gray-400">{formatDate(d.created_at)}</p>
                </div>
                <Badge className={statusColor(d.status)}>
                  {d.status.replace("_", " ")}
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
