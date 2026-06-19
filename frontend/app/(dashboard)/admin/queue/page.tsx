"use client";

import { useQuery } from "@tanstack/react-query";
import { adminGetQueueHealth } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

function StatBox({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-5 py-4 text-center">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}

export default function AdminQueuePage() {
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["admin-queue-health"],
    queryFn: adminGetQueueHealth,
    refetchInterval: 15000,
  });

  const lastRefresh = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : "—";

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Queue health</h1>
          <p className="text-gray-400 text-sm mt-0.5">Auto-refreshes every 15 s · Last update: {lastRefresh}</p>
        </div>
        {isLoading && (
          <div className="h-5 w-5 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatBox label="Active tasks" value={data?.active_tasks ?? "—"} />
        <StatBox label="Reserved (prefetched)" value={data?.reserved_tasks ?? "—"} />
        <StatBox label="Pending in broker" value={data?.pending_in_broker ?? "—"} />
      </div>

      {/* Workers */}
      <Card>
        <CardHeader>
          <CardTitle>Workers</CardTitle>
        </CardHeader>
        {!data || data.workers.length === 0 ? (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            No workers online. The Celery worker may be down — check your deployment.
          </div>
        ) : (
          <div className="space-y-3">
            {data.workers.map((w) => (
              <div
                key={w.name}
                className="flex items-center justify-between rounded-xl border border-gray-200 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900 font-mono">{w.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {w.active_tasks} active
                    {w.processed != null ? ` · ${w.processed.toLocaleString()} total processed` : ""}
                  </p>
                </div>
                <Badge className="bg-green-100 text-green-800">online</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Guidance */}
      <Card className="bg-gray-50 border-gray-200">
        <p className="text-xs text-gray-500 leading-relaxed">
          <span className="font-semibold text-gray-700">Reading this page:</span>{" "}
          <strong>Active</strong> tasks are currently being processed by a worker.{" "}
          <strong>Reserved</strong> tasks have been picked up but not started (worker prefetch).{" "}
          <strong>Pending in broker</strong> are waiting in Redis for a worker slot.
          If pending keeps growing and workers are online, scale up the worker pool in your
          Fly.io deployment.
        </p>
      </Card>
    </div>
  );
}
