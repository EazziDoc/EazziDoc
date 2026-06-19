"use client";

import { useMutation } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { listAvailableDoctors, messageDoctor } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";

export default function FindDoctorPage() {
  const { data: doctors = [], isLoading } = useQuery({
    queryKey: ["doctors"],
    queryFn: listAvailableDoctors,
  });

  const [activeId, setActiveId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  const { mutateAsync, isPending } = useMutation({
    mutationFn: ({ id, msg }: { id: string; msg: string }) => messageDoctor(id, msg),
    onSuccess: (_, { id }) => {
      setSent(id);
      setActiveId(null);
      setMessage("");
    },
  });

  async function handleSend(doctorId: string) {
    if (!message.trim()) return;
    await mutateAsync({ id: doctorId, msg: message });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Find a doctor</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Browse available doctors, book a consultation, or send them a message.
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      ) : doctors.length === 0 ? (
        <Card>
          <p className="text-center text-gray-400 py-8 text-sm">
            No doctors are available right now. Check back soon.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {doctors.map((doc) => (
            <Card key={doc.id} className="flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-gray-900">
                    Dr. {doc.first_name} {doc.last_name}
                  </p>
                  {doc.specialty && (
                    <p className="text-sm text-gray-500 mt-0.5">{doc.specialty}</p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1">
                  {doc.is_verified && (
                    <Badge className="bg-green-100 text-green-800 text-xs">Verified</Badge>
                  )}
                  <Badge className="bg-blue-100 text-blue-800 text-xs">Available</Badge>
                </div>
              </div>

              {sent === doc.id && (
                <p className="text-xs text-green-700 bg-green-50 rounded-lg px-3 py-2">
                  Message sent — Dr. {doc.last_name} will receive it by email.
                </p>
              )}

              {activeId === doc.id ? (
                <div className="space-y-2">
                  <Textarea
                    id={`msg-${doc.id}`}
                    label="Your message"
                    placeholder="Type your message to the doctor…"
                    rows={3}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      loading={isPending}
                      onClick={() => handleSend(doc.id)}
                      className="flex-1 text-sm py-2"
                    >
                      Send message
                    </Button>
                    <button
                      type="button"
                      onClick={() => { setActiveId(null); setMessage(""); }}
                      className="text-sm text-gray-400 hover:text-gray-600 px-3"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-auto flex gap-2">
                  <Link
                    href={`/patient/appointments?doctor_id=${doc.id}`}
                    className="flex-1 rounded-lg bg-primary-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-primary-700 transition-colors"
                  >
                    Book appointment
                  </Link>
                  <button
                    type="button"
                    onClick={() => { setActiveId(doc.id); setSent(null); }}
                    className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    Message
                  </button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
