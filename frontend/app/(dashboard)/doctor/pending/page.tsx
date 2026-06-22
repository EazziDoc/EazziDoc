"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { getDoctorProfile } from "@/lib/api";
import { Card } from "@/components/ui/card";
import Link from "next/link";

const STATUS_CONFIG = {
  pending_review: {
    icon: "⏳",
    title: "Registration under review",
    color: "bg-yellow-50 border-yellow-200",
    textColor: "text-yellow-800",
    description:
      "Your registration is currently being reviewed by our admin team. This typically takes 1–3 business days. You'll receive an email once a decision has been made.",
  },
  approved: {
    icon: "✅",
    title: "Registration approved",
    color: "bg-green-50 border-green-200",
    textColor: "text-green-800",
    description: "Your registration has been approved. You can now receive patient bookings.",
  },
  rejected: {
    icon: "❌",
    title: "Registration not approved",
    color: "bg-red-50 border-red-200",
    textColor: "text-red-800",
    description: "Your registration was not approved. Please review the reason below and contact support if you have questions.",
  },
};

export default function DoctorPendingPage() {
  const { user } = useAuth();
  const { data: profile } = useQuery({
    queryKey: ["doctor-profile"],
    queryFn: getDoctorProfile,
    enabled: !!user,
  });

  const status = (profile?.registration_status ?? "pending_review") as keyof typeof STATUS_CONFIG;
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending_review;

  return (
    <div className="max-w-lg mx-auto space-y-6 pt-8">
      <div className="text-center space-y-2">
        <div className="text-5xl">{cfg.icon}</div>
        <h1 className="text-2xl font-bold text-gray-900">{cfg.title}</h1>
      </div>

      <Card className={`border ${cfg.color}`}>
        <p className={`text-sm leading-relaxed ${cfg.textColor}`}>{cfg.description}</p>

        {status === "rejected" && profile?.rejection_reason && (
          <div className="mt-4 rounded-lg bg-red-100 border border-red-200 px-4 py-3">
            <p className="text-xs font-semibold text-red-700 uppercase mb-1">Reason</p>
            <p className="text-sm text-red-700">{profile.rejection_reason}</p>
          </div>
        )}
      </Card>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">What you submitted</h2>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Name</span>
            <span className="text-gray-900">{profile?.first_name} {profile?.last_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Specialty</span>
            <span className="text-gray-900">{profile?.specialty ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Licence number</span>
            <span className="text-gray-900">{profile?.license_number ?? "—"}</span>
          </div>
          {profile?.qualifications && profile.qualifications.length > 0 && (
            <div>
              <span className="text-gray-500 block mb-1">Qualifications</span>
              <ul className="space-y-0.5 pl-2">
                {profile.qualifications.map((q: string) => (
                  <li key={q} className="text-gray-700 text-xs">• {q}</li>
                ))}
              </ul>
            </div>
          )}
          {profile?.other_qualifications && (
            <div>
              <span className="text-gray-500 block mb-1">Other qualifications</span>
              <p className="text-gray-700 text-xs">{profile.other_qualifications}</p>
            </div>
          )}
        </div>
      </Card>

      {status === "approved" && (
        <Link
          href="/doctor"
          className="block w-full text-center rounded-xl bg-primary-600 px-6 py-3 text-sm font-semibold text-white hover:bg-primary-700 transition-colors"
        >
          Go to dashboard →
        </Link>
      )}

      <p className="text-center text-xs text-gray-400">
        Questions?{" "}
        <a href="mailto:support@eazzidoc.com" className="underline hover:text-gray-600">
          Contact support
        </a>
      </p>
    </div>
  );
}
