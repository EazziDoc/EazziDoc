"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getDiagnosis } from "@/lib/api";
import type { DiagnosisReport } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime, statusColor } from "@/lib/utils";

const urgencyColor: Record<string, string> = {
  routine: "bg-green-100 text-green-800",
  urgent: "bg-orange-100 text-orange-800",
  emergent: "bg-red-100 text-red-800",
};

function ReportSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{title}</h3>
      {children}
    </div>
  );
}

function ReportView({ report, model_used, confidence_score }: {
  report: DiagnosisReport;
  model_used: string | null;
  confidence_score: number | null;
}) {
  if (report.error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        AI analysis failed: {report.error}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Metadata row */}
      <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
        {model_used && <span>Model: <span className="font-medium text-gray-700">{model_used}</span></span>}
        {confidence_score != null && (
          <span>Confidence: <span className="font-medium text-gray-700">{Math.round(confidence_score * 100)}%</span></span>
        )}
        {report.urgency && (
          <Badge className={urgencyColor[report.urgency] ?? ""}>
            {report.urgency.charAt(0).toUpperCase() + report.urgency.slice(1)}
          </Badge>
        )}
      </div>

      {report.summary && (
        <ReportSection title="Summary">
          <p className="text-gray-700 text-sm leading-relaxed">{report.summary}</p>
        </ReportSection>
      )}

      {report.impression && (
        <ReportSection title="Impression">
          <p className="text-gray-700 text-sm leading-relaxed">{report.impression}</p>
        </ReportSection>
      )}

      {report.findings && report.findings.length > 0 && (
        <ReportSection title="Findings">
          <ul className="space-y-1">
            {report.findings.map((f, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-primary-500" />
                {f}
              </li>
            ))}
          </ul>
        </ReportSection>
      )}

      {report.differential_diagnoses && report.differential_diagnoses.length > 0 && (
        <ReportSection title="Differential diagnoses">
          <ul className="space-y-1">
            {report.differential_diagnoses.map((d, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-gray-400" />
                {d}
              </li>
            ))}
          </ul>
        </ReportSection>
      )}

      {report.recommendations && report.recommendations.length > 0 && (
        <ReportSection title="Recommendations">
          <ul className="space-y-1">
            {report.recommendations.map((r, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <span className="text-primary-600 flex-shrink-0">→</span>
                {r}
              </li>
            ))}
          </ul>
        </ReportSection>
      )}

      {report.patient_notes && (
        <ReportSection title="Patient notes submitted">
          <p className="text-gray-500 text-sm italic">{report.patient_notes}</p>
        </ReportSection>
      )}
    </div>
  );
}

export default function DiagnosisDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: dx, isLoading } = useQuery({
    queryKey: ["diagnosis", id],
    queryFn: () => getDiagnosis(id),
    // Poll every 5 s while AI is still processing
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 5000 : false;
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!dx) {
    return (
      <div className="text-center py-24 text-gray-400">
        Diagnosis not found.{" "}
        <Link href="/patient/diagnoses" className="text-primary-600 hover:underline">
          Back
        </Link>
      </div>
    );
  }

  const isPending = dx.status === "pending" || dx.status === "processing";

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link href="/patient/diagnoses" className="text-sm text-gray-400 hover:text-gray-600">
            ← All diagnoses
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1 capitalize">
            {dx.modality?.replace(/_/g, " ") ?? "Medical imaging"}
          </h1>
          <p className="text-gray-400 text-sm mt-0.5">{formatDateTime(dx.created_at)}</p>
        </div>
        <Badge className={statusColor(dx.status)}>{dx.status.replace(/_/g, " ")}</Badge>
      </div>

      {/* Image count indicator */}
      <Card>
        <p className="text-sm text-gray-500">
          <span className="font-medium text-gray-700">{dx.image_keys.length}</span>{" "}
          image{dx.image_keys.length !== 1 ? "s" : ""} submitted for analysis
        </p>
      </Card>

      {/* AI report */}
      <Card>
        <CardHeader>
          <CardTitle>AI analysis report</CardTitle>
        </CardHeader>
        {isPending ? (
          <div className="flex items-center gap-3 py-6 text-gray-500">
            <div className="h-5 w-5 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
            <span className="text-sm">AI is analysing your images… this usually takes 30–60 seconds.</span>
          </div>
        ) : dx.status === "failed" ? (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            Analysis failed. Please try uploading again or contact support.
          </div>
        ) : (
          <ReportView
            report={dx.report ?? {}}
            model_used={dx.model_used}
            confidence_score={dx.confidence_score}
          />
        )}
      </Card>

      {/* Doctor review notes (if any) */}
      {dx.doctor_notes && (
        <Card>
          <CardHeader>
            <CardTitle>Doctor review</CardTitle>
          </CardHeader>
          <p className="text-sm text-gray-700 leading-relaxed">{dx.doctor_notes}</p>
          <Badge className={`mt-3 ${statusColor(dx.status)}`}>
            {dx.status.replace(/_/g, " ")}
          </Badge>
        </Card>
      )}

      {/* Book appointment CTA */}
      {!isPending && dx.status !== "failed" && (
        <div className="rounded-xl border border-primary-100 bg-primary-50 p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-primary-900">Want a doctor to review this?</p>
            <p className="text-xs text-primary-700 mt-0.5">Book a consultation and share this diagnosis.</p>
          </div>
          <Link
            href={`/patient/appointments?diagnosis_id=${dx.id}`}
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Book appointment
          </Link>
        </div>
      )}
    </div>
  );
}
