"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getPendingQueue, reviewDiagnosis } from "@/lib/api";
import type { Diagnosis } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { formatDate } from "@/lib/utils";

const urgencyColor: Record<string, string> = {
  routine: "bg-green-100 text-green-800",
  urgent: "bg-orange-100 text-orange-800",
  emergent: "bg-red-100 text-red-800",
};

const REVIEW_STATUSES = [
  { value: "confirmed", label: "Confirm AI report" },
  { value: "overridden", label: "Override AI report" },
  { value: "flagged", label: "Flag for second opinion" },
  { value: "under_review", label: "Keep under review" },
] as const;

function DiagnosisCard({ dx }: { dx: Diagnosis }) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<string>("confirmed");
  const [expanded, setExpanded] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const { mutateAsync, isPending } = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { notes: string; status: string } }) =>
      reviewDiagnosis(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["queue"] }),
  });

  async function handleReview(e: React.FormEvent) {
    e.preventDefault();
    if (!notes.trim()) { setSubmitError("Notes are required before submitting a review."); return; }
    setSubmitError("");
    try {
      await mutateAsync({ id: dx.id, data: { notes: notes.trim(), status } });
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Review failed");
    }
  }

  const report = dx.report ?? {};

  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold text-gray-900 capitalize">
            {dx.modality?.replace(/_/g, " ") ?? "Unknown modality"}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">{formatDate(dx.created_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          {report.urgency && (
            <Badge className={urgencyColor[report.urgency] ?? ""}>{report.urgency}</Badge>
          )}
          {dx.confidence_score != null && (
            <span className="text-xs text-gray-500">
              {Math.round(dx.confidence_score * 100)}% confidence
            </span>
          )}
        </div>
      </div>

      {/* AI report summary */}
      {report.summary && (
        <div>
          <p className="text-sm text-gray-700 leading-relaxed line-clamp-3">{report.summary}</p>
          {!expanded && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="text-xs text-primary-600 hover:underline mt-1"
            >
              Show full report
            </button>
          )}
        </div>
      )}

      {/* Full report */}
      {expanded && (
        <div className="rounded-lg bg-gray-50 p-4 space-y-4 text-sm">
          {report.impression && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Impression</p>
              <p className="text-gray-600">{report.impression}</p>
            </div>
          )}
          {report.findings && report.findings.length > 0 && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Findings</p>
              <ul className="space-y-1">
                {report.findings.map((f, i) => (
                  <li key={i} className="flex gap-2 text-gray-600">
                    <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-primary-400" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.differential_diagnoses && report.differential_diagnoses.length > 0 && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Differentials</p>
              <ul className="space-y-1">
                {report.differential_diagnoses.map((d, i) => (
                  <li key={i} className="text-gray-600">• {d}</li>
                ))}
              </ul>
            </div>
          )}
          {report.recommendations && report.recommendations.length > 0 && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Recommendations</p>
              <ul className="space-y-1">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="text-gray-600">→ {r}</li>
                ))}
              </ul>
            </div>
          )}
          {report.patient_notes && (
            <div>
              <p className="font-medium text-gray-700 mb-1">Patient notes</p>
              <p className="text-gray-500 italic">{report.patient_notes}</p>
            </div>
          )}
          <button
            type="button"
            onClick={() => setExpanded(false)}
            className="text-xs text-gray-400 hover:underline"
          >
            Collapse
          </button>
        </div>
      )}

      {/* Review form */}
      <form onSubmit={handleReview} className="space-y-3 border-t border-gray-100 pt-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Review decision</label>
          <div className="flex flex-wrap gap-2">
            {REVIEW_STATUSES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setStatus(s.value)}
                className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                  status === s.value
                    ? "bg-primary-600 border-primary-600 text-white"
                    : "border-gray-300 text-gray-600 hover:border-primary-400"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <Textarea
          id={`notes-${dx.id}`}
          label="Clinical notes (required)"
          placeholder="Add your clinical assessment, corrections, or additional observations…"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          required
        />

        {submitError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{submitError}</p>
        )}

        <Button type="submit" loading={isPending} size="sm">
          Submit review
        </Button>
      </form>
    </Card>
  );
}

export default function QueuePage() {
  const { data: queue = [], isLoading } = useQuery({
    queryKey: ["queue"],
    queryFn: getPendingQueue,
    refetchInterval: 30000,
  });

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Review queue</h1>
          <p className="text-gray-500 mt-1 text-sm">AI-completed diagnoses awaiting your clinical review.</p>
        </div>
        {queue.length > 0 && (
          <Badge className="bg-yellow-100 text-yellow-800">{queue.length} pending</Badge>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      ) : queue.length === 0 ? (
        <Card>
          <p className="text-center text-gray-400 py-8 text-sm">
            Queue is empty. All diagnoses have been reviewed.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {queue.map((dx) => (
            <DiagnosisCard key={dx.id} dx={dx} />
          ))}
        </div>
      )}
    </div>
  );
}
