"use client";

import { useQuery } from "@tanstack/react-query";
import { listMyPatients } from "@/lib/api";
import { Card } from "@/components/ui/card";

export default function MyPatientsPage() {
  const { data: patients = [], isLoading } = useQuery({
    queryKey: ["my-patients"],
    queryFn: listMyPatients,
  });

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
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {patients.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">
                    {p.first_name} {p.last_name}
                  </td>
                  <td className="px-6 py-4 text-gray-500 capitalize">
                    {p.gender?.replace("_", " ") ?? "—"}
                  </td>
                  <td className="px-6 py-4 text-gray-500">{p.country ?? "—"}</td>
                  <td className="px-6 py-4 text-gray-500">{p.phone ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
