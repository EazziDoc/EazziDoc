"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  completeAppointment,
  confirmAppointment,
  doctorCancelAppointment,
  listDoctorAppointments,
} from "@/lib/api";
import type { Appointment } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatDateTime, statusColor } from "@/lib/utils";

function ActionButton({
  label,
  onClick,
  variant = "outline",
}: {
  label: string;
  onClick: () => void;
  variant?: "primary" | "outline" | "danger";
}) {
  const base = "rounded-lg px-3 py-1 text-xs font-medium transition-colors";
  const styles = {
    primary: `${base} bg-primary-600 text-white hover:bg-primary-700`,
    outline: `${base} border border-gray-300 text-gray-700 hover:bg-gray-50`,
    danger: `${base} text-red-600 hover:text-red-700 hover:underline`,
  };
  return (
    <button type="button" onClick={onClick} className={styles[variant]}>
      {label}
    </button>
  );
}

function AppointmentRow({ a }: { a: Appointment }) {
  const qc = useQueryClient();
  const [confirmCancel, setConfirmCancel] = useState(false);

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["doctor-appointments"] });
  }

  const { mutate: confirm } = useMutation({ mutationFn: confirmAppointment, onSuccess: invalidate });
  const { mutate: complete } = useMutation({ mutationFn: completeAppointment, onSuccess: invalidate });
  const { mutate: cancel } = useMutation({ mutationFn: doctorCancelAppointment, onSuccess: invalidate });

  const canCancel = a.status === "booked" || a.status === "confirmed";

  return (
    <div className="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4">
      <div className="space-y-0.5">
        <p className="text-sm font-semibold text-gray-900">{formatDateTime(a.scheduled_at)}</p>
        <p className="text-xs text-gray-500">{a.duration_mins} min session</p>
        {a.notes && <p className="text-xs text-gray-400 italic mt-1">{a.notes}</p>}
      </div>

      <div className="flex flex-col items-end gap-2">
        <Badge className={statusColor(a.status)}>{a.status}</Badge>
        <div className="flex gap-2">
          {a.status === "booked" && (
            <ActionButton label="Confirm" onClick={() => confirm(a.id)} variant="primary" />
          )}
          {a.status === "confirmed" && (
            <ActionButton label="Mark complete" onClick={() => complete(a.id)} variant="primary" />
          )}
          {canCancel && (
            <ActionButton label="Cancel" onClick={() => setConfirmCancel(true)} variant="danger" />
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        title="Cancel appointment?"
        description="This will cancel the appointment for you and the patient. The action cannot be undone."
        confirmLabel="Yes, cancel"
        destructive
        onConfirm={() => { setConfirmCancel(false); cancel(a.id); }}
        onCancel={() => setConfirmCancel(false)}
      />
    </div>
  );
}

export default function DoctorAppointmentsPage() {
  const { data: appointments = [], isLoading } = useQuery({
    queryKey: ["doctor-appointments"],
    queryFn: listDoctorAppointments,
  });

  const groups = {
    active: appointments.filter((a) => ["booked", "confirmed"].includes(a.status)),
    completed: appointments.filter((a) => a.status === "completed"),
    cancelled: appointments.filter((a) => a.status === "cancelled"),
  };

  return (
    <div className="max-w-3xl space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">My appointments</h1>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      ) : appointments.length === 0 ? (
        <Card>
          <p className="text-center text-gray-400 py-8 text-sm">No appointments yet.</p>
        </Card>
      ) : (
        <>
          {groups.active.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-base font-semibold text-gray-800">
                Upcoming ({groups.active.length})
              </h2>
              {groups.active.map((a) => (
                <AppointmentRow key={a.id} a={a} />
              ))}
            </section>
          )}

          {groups.completed.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-base font-semibold text-gray-800">
                Completed ({groups.completed.length})
              </h2>
              {groups.completed.map((a) => (
                <AppointmentRow key={a.id} a={a} />
              ))}
            </section>
          )}

          {groups.cancelled.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-base font-semibold text-gray-400">
                Cancelled ({groups.cancelled.length})
              </h2>
              {groups.cancelled.map((a) => (
                <AppointmentRow key={a.id} a={a} />
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}
