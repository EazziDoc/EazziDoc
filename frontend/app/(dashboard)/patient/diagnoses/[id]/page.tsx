"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useParams } from "next/navigation";
import { getDiagnosis, getDiagnosisSegmentationUrl } from "@/lib/api";
import type { DiagnosisReport, SpecialistModel } from "@/lib/types";
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

function SpecialistPanel({ specialist }: { specialist: SpecialistModel }) {
  const sorted = Object.entries(specialist.all_findings).sort((a, b) => b[1] - a[1]);
  return (
    <div className="rounded-lg bg-blue-50 border border-blue-100 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
          Specialist model · {specialist.model}
        </p>
        <Badge className="bg-blue-100 text-blue-800 text-xs">
          {specialist.top_finding} — {Math.round(specialist.top_confidence * 100)}%
        </Badge>
      </div>
      <div className="space-y-1.5">
        {sorted.map(([label, score]) => (
          <div key={label} className="flex items-center gap-3">
            <span className="w-40 shrink-0 text-xs text-gray-700 truncate">{label}</span>
            <div className="flex-1 h-1.5 rounded-full bg-blue-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500"
                style={{ width: `${Math.round(score * 100)}%` }}
              />
            </div>
            <span className="w-9 text-right text-xs text-gray-500">
              {Math.round(score * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SegmentationOverlay({ diagnosisId }: { diagnosisId: string }) {
  const [overlayUrl, setOverlayUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [shown, setShown] = useState(false);

  async function handleToggle() {
    if (shown) { setShown(false); return; }
    if (overlayUrl) { setShown(true); return; }
    setLoading(true);
    try {
      const { url } = await getDiagnosisSegmentationUrl(diagnosisId);
      setOverlayUrl(url);
      setShown(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={handleToggle}
        disabled={loading}
        className="text-sm font-medium text-primary-600 hover:underline disabled:opacity-50"
      >
        {loading ? "Loading overlay…" : shown ? "Hide AI segmentation overlay" : "Show AI segmentation overlay"}
      </button>
      {shown && overlayUrl && (
        <div className="rounded-lg overflow-hidden border border-gray-200">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={overlayUrl} alt="MedSAM segmentation overlay" className="w-full" />
          <p className="text-xs text-gray-400 text-center py-2 bg-gray-50">
            AI segmentation — highlighted region indicates area of interest detected by MedSAM
          </p>
        </div>
      )}
    </div>
  );
}

function ReportView({ report, model_used, confidence_score, diagnosisId }: {
  report: DiagnosisReport;
  model_used: string | null;
  confidence_score: number | null;
  diagnosisId: string;
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

      {/* Specialist model findings */}
      {report.specialist_model && <SpecialistPanel specialist={report.specialist_model} />}

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

      {/* MedSAM segmentation overlay (only shown when key present in report) */}
      {report.segmentation_key && (
        <ReportSection title="AI segmentation overlay">
          <SegmentationOverlay diagnosisId={diagnosisId} />
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
            diagnosisId={dx.id}
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
