"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { listDiagnoses } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, statusColor } from "@/lib/utils";

export default function DiagnosesPage() {
  const { data: diagnoses = [], isLoading } = useQuery({
    queryKey: ["diagnoses"],
    queryFn: listDiagnoses,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My diagnoses</h1>
        <Link
          href="/patient/upload"
          className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          + New
        </Link>
      </div>

      <Card className="p-0">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
          </div>
        ) : diagnoses.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-400 text-sm">No diagnoses yet.</p>
            <Link
              href="/patient/upload"
              className="mt-3 inline-block text-sm text-primary-600 hover:underline"
            >
              Upload your first medical image →
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left font-medium text-gray-500 px-6 py-3">Date</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Modality</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Images</th>
                <th className="text-left font-medium text-gray-500 px-6 py-3">Status</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {diagnoses.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-gray-700">{formatDate(d.created_at)}</td>
                  <td className="px-6 py-4 text-gray-900 capitalize">
                    {d.modality?.replace("_", " ") ?? "—"}
                  </td>
                  <td className="px-6 py-4 text-gray-500">{d.image_keys.length}</td>
                  <td className="px-6 py-4">
                    <Badge className={statusColor(d.status)}>
                      {d.status.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      href={`/patient/diagnoses/${d.id}`}
                      className="text-primary-600 hover:underline"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
