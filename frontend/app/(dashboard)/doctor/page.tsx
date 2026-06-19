"use client";

import { useQuery } from "@tanstack/react-query";
import { Calendar, ClipboardList, UserCheck } from "lucide-react";
import Link from "next/link";
import { listDoctorAppointments, getPendingQueue } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, formatDateTime, statusColor } from "@/lib/utils";

export default function DoctorDashboard() {
  const { user } = useAuth();

  const { data: queue = [] } = useQuery({
    queryKey: ["queue"],
    queryFn: getPendingQueue,
  });

  const { data: appointments = [] } = useQuery({
    queryKey: ["doctor-appointments"],
    queryFn: listDoctorAppointments,
  });

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

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Pending reviews", value: queue.length, icon: ClipboardList, color: "text-yellow-600 bg-yellow-50" },
          { label: "Upcoming appointments", value: upcoming, icon: Calendar, color: "text-blue-600 bg-blue-50" },
          { label: "Total today", value: appointments.filter((a) => {
              const d = new Date(a.scheduled_at);
              const now = new Date();
              return d.toDateString() === now.toDateString();
            }).length, icon: UserCheck, color: "text-green-600 bg-green-50" },
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
            href="/doctor/queue"
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            <ClipboardList className="h-4 w-4" /> Review queue
          </Link>
          <Link
            href="/doctor/appointments"
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Calendar className="h-4 w-4" /> Appointments
          </Link>
        </div>
      </Card>

      {/* Pending queue preview */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Pending reviews</h2>
          <Link href="/doctor/queue" className="text-sm text-primary-600 hover:underline">
            View all
          </Link>
        </div>
        {queue.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No pending diagnoses. Well done!</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {queue.slice(0, 5).map((d) => (
              <Link
                key={d.id}
                href={`/doctor/queue`}
                className="flex items-center justify-between py-3 hover:bg-gray-50 rounded-lg px-2 -mx-2 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900 capitalize">
                    {d.modality?.replace(/_/g, " ") ?? "Unknown modality"}
                  </p>
                  <p className="text-xs text-gray-400">{formatDate(d.created_at)}</p>
                </div>
                <Badge className={statusColor(d.status)}>{d.status.replace(/_/g, " ")}</Badge>
              </Link>
            ))}
          </div>
        )}
      </Card>

      {/* Upcoming appointments preview */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Upcoming appointments</h2>
          <Link href="/doctor/appointments" className="text-sm text-primary-600 hover:underline">
            View all
          </Link>
        </div>
        {upcoming === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No upcoming appointments.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {appointments
              .filter((a) => ["booked", "confirmed"].includes(a.status))
              .slice(0, 5)
              .map((a) => (
                <div key={a.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDateTime(a.scheduled_at)}
                    </p>
                    <p className="text-xs text-gray-400">{a.duration_mins} min</p>
                  </div>
                  <Badge className={statusColor(a.status)}>{a.status}</Badge>
                </div>
              ))}
          </div>
        )}
      </Card>
    </div>
  );
}
