"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  bookAppointment,
  cancelAppointment,
  listAppointments,
  listAvailableDoctors,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { formatDateTime, statusColor } from "@/lib/utils";

function BookingForm({
  prefillDiagnosisId,
  prefillDoctorId,
}: {
  prefillDiagnosisId: string | null;
  prefillDoctorId: string | null;
}) {
  const qc = useQueryClient();
  const { data: doctors = [] } = useQuery({
    queryKey: ["doctors"],
    queryFn: listAvailableDoctors,
  });

  const [doctorId, setDoctorId] = useState(prefillDoctorId ?? "");
  const [scheduledAt, setScheduledAt] = useState("");
  const [duration, setDuration] = useState(30);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const { mutateAsync, isPending } = useMutation({
    mutationFn: bookAppointment,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
      setDoctorId("");
      setScheduledAt("");
      setNotes("");
    },
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!doctorId || !scheduledAt) { setError("Select a doctor and date/time."); return; }
    setError("");
    try {
      await mutateAsync({
        doctor_id: doctorId,
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_mins: duration,
        notes: notes.trim() || undefined,
        ...(prefillDiagnosisId ? { diagnosis_id: prefillDiagnosisId } : {}),
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Booking failed");
    }
  }

  const minDate = new Date();
  minDate.setMinutes(minDate.getMinutes() + 30);
  const minStr = minDate.toISOString().slice(0, 16);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Book a consultation</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Doctor</label>
          <select
            value={doctorId}
            onChange={(e) => setDoctorId(e.target.value)}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="">Select a doctor…</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                Dr. {d.first_name} {d.last_name}
                {d.specialty ? ` — ${d.specialty}` : ""}
              </option>
            ))}
          </select>
        </div>

        <Input
          id="scheduled_at"
          type="datetime-local"
          label="Date & time"
          min={minStr}
          value={scheduledAt}
          onChange={(e) => setScheduledAt(e.target.value)}
          required
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Duration: {duration} min
          </label>
          <input
            type="range"
            min={15}
            max={120}
            step={15}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="w-full accent-primary-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>15 min</span>
            <span>120 min</span>
          </div>
        </div>

        <Textarea
          id="notes"
          label="Notes (optional)"
          placeholder="Reason for appointment or anything you'd like the doctor to know…"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />

        {prefillDiagnosisId && (
          <p className="text-xs text-primary-700 bg-primary-50 rounded-lg px-3 py-2">
            This appointment will be linked to your recent diagnosis.
          </p>
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}

        <Button type="submit" loading={isPending} className="w-full">
          Confirm booking
        </Button>
      </form>
    </Card>
  );
}

function AppointmentList() {
  const qc = useQueryClient();
  const { data: appointments = [], isLoading } = useQuery({
    queryKey: ["appointments"],
    queryFn: listAppointments,
  });

  const { mutate: cancel } = useMutation({
    mutationFn: cancelAppointment,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (appointments.length === 0) {
    return <p className="text-center text-sm text-gray-400 py-8">No appointments yet.</p>;
  }

  return (
    <div className="space-y-3">
      {appointments.map((a) => (
        <div
          key={a.id}
          className="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4"
        >
          <div>
            <p className="text-sm font-medium text-gray-900">
              {formatDateTime(a.scheduled_at)}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">{a.duration_mins} min</p>
            {a.notes && (
              <p className="text-xs text-gray-400 mt-1 italic">{a.notes}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge className={statusColor(a.status)}>{a.status}</Badge>
            {["booked", "confirmed"].includes(a.status) && (
              <button
                onClick={() => cancel(a.id)}
                className="text-xs text-red-500 hover:underline"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function AppointmentsPage() {
  const params = useSearchParams();
  const diagnosisId = params.get("diagnosis_id");
  const doctorId = params.get("doctor_id");

  return (
    <div className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Appointments</h1>
      <BookingForm prefillDiagnosisId={diagnosisId} prefillDoctorId={doctorId} />
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">My appointments</h2>
        <AppointmentList />
      </div>
    </div>
  );
}

export default function AppointmentsPageWrapper() {
  return (
    <Suspense>
      <AppointmentsPage />
    </Suspense>
  );
}
