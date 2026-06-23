"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { listMyPatients, messageDoctorPatient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";

export default function MyPatientsPage() {
  const { data: patients = [], isLoading } = useQuery({
    queryKey: ["my-patients"],
    queryFn: listMyPatients,
  });

  const [activeId, setActiveId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState("");

  const { mutateAsync, isPending } = useMutation({
    mutationFn: ({ id, msg }: { id: string; msg: string }) => messageDoctorPatient(id, msg),
    onSuccess: (_, { id }) => {
      setSent(id);
      setActiveId(null);
      setMessage("");
      setError("");
    },
    onError: () => setError("Failed to send message. Please try again."),
  });

  async function handleSend(patientId: string) {
    if (!message.trim()) return;
    await mutateAsync({ id: patientId, msg: message });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My patients</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Patients linked to you via appointments or diagnoses you have reviewed.
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      ) : patients.length === 0 ? (
        <Card>
          <p className="text-center text-gray-400 py-8 text-sm">
            No patients yet. They will appear here once you review a diagnosis or confirm an
            appointment.
          </p>
        </Card>
      ) : (
        <Card className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left font-medium text-gray-500 px-6 py-3">Name</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Gender</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Country</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Phone</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {patients.map((p) => (
                <>
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900">
                      {p.first_name} {p.last_name}
                    </td>
                    <td className="px-6 py-4 text-gray-500 capitalize">
                      {p.gender?.replace("_", " ") ?? "—"}
                    </td>
                    <td className="px-6 py-4 text-gray-500">{p.country ?? "—"}</td>
                    <td className="px-6 py-4 text-gray-500">{p.phone ?? "—"}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-4">
                        <Link
                          href={`/doctor/patients/${p.id}`}
                          className="text-xs text-primary-600 font-medium hover:underline"
                        >
                          View →
                        </Link>
                        {sent === p.id ? (
                          <span className="text-xs text-green-600 font-medium">Sent ✓</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setActiveId(activeId === p.id ? null : p.id);
                              setMessage("");
                              setError("");
                            }}
                            className="text-xs text-gray-500 font-medium hover:underline"
                          >
                            {activeId === p.id ? "Cancel" : "Message"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>

                  {activeId === p.id && (
                    <tr key={`${p.id}-form`}>
                      <td colSpan={5} className="px-6 py-4 bg-gray-50 border-t border-gray-100">
                        <div className="max-w-lg space-y-3">
                          <Textarea
                            id={`msg-${p.id}`}
                            label={`Message to ${p.first_name} ${p.last_name}`}
                            placeholder="Type your message — it will be delivered to the patient's email…"
                            rows={3}
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                          />
                          {error && (
                            <p className="text-xs text-red-600">{error}</p>
                          )}
                          <Button
                            type="button"
                            loading={isPending}
                            onClick={() => handleSend(p.id)}
                            className="text-sm py-2"
                          >
                            Send message
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
