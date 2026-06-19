"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { listAvailableDoctors } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export default function FindDoctorPage() {
  const { data: doctors = [], isLoading } = useQuery({
    queryKey: ["doctors"],
    queryFn: listAvailableDoctors,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Find a doctor</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Browse available doctors and book a consultation.
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
              <Link
                href={`/patient/appointments?doctor_id=${doc.id}`}
                className="mt-auto rounded-lg bg-primary-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-primary-700 transition-colors"
              >
                Book appointment
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
