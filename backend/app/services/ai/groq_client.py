"""Groq Llama 3.3 70b — primary AI report generator.

Produces structured JSON diagnostic reports grounded on specialist model
findings (TorchXRayVision, RETFound, HAM10000) and any patient-supplied notes.
Returns {} on failure so the caller can mark the diagnosis as flagged.
"""

import json
import logging

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)


_SYSTEM = """
You are a board-certified radiologist AI assistant. Your role is to analyse \
medical imaging results and produce a clear, clinically accurate diagnostic report.

You will receive:
- The imaging modality (e.g. chest X-ray, fundus, skin, brain MRI, mammography)
- Findings from a specialist computer-vision model (where available)
- Any notes the patient has provided

Your output must be a single valid JSON object with exactly these keys:

{
  "summary":               "<1–2 sentence plain-language overview of the case>",
  "findings":              ["<specific observation 1>", "<specific observation 2>", ...],
  "impression":            "<primary clinical impression — the most likely diagnosis>",
  "differential_diagnoses":["<alternative diagnosis 1>", "<alternative diagnosis 2>"],
  "recommendations":       ["<next clinical action 1>", "<next clinical action 2>", ...],
  "urgency":               "<routine | urgent | emergent>",
  "confidence":            <float 0.0–1.0>
}

Urgency guide:
- routine   → no acute findings; routine follow-up is sufficient
- urgent    → significant findings requiring attention within 24–48 hours
- emergent  → life-threatening findings requiring immediate intervention

Rules:
- Return ONLY the JSON object. No markdown fences, no preamble, no explanation.
- Base findings strictly on the specialist model data provided; do not invent findings.
- If specialist data is absent, note this limitation in the summary and lower the confidence score.
- confidence reflects the certainty of the impression given available data (not image quality).
"""


def _build_user_message(
    modality: str,
    patient_notes: str | None,
    specialist: dict | None,
) -> str:
    lines = [
        f"Imaging modality : {modality}",
        f"Patient notes    : {patient_notes or 'None provided'}",
        "",
    ]

    if specialist:
        top = specialist["top_finding"]
        conf = specialist["top_confidence"]
        model = specialist["model"]
        detail = "\n".join(
            f"  • {finding}: {score:.0%}" for finding, score in specialist["all_findings"].items()
        )
        lines += [
            "Specialist model findings (ground your report on these):",
            f"  Model       : {model}",
            f"  Top finding : {top} ({conf:.0%} confidence)",
            "  All findings:",
            detail,
        ]
    else:
        lines.append(
            "Specialist model : not available for this modality — "
            "base your report on modality context and patient notes only."
        )

    lines += [
        "",
        "Generate the diagnostic report now.",
    ]

    return "\n".join(lines)


def _strip_fences(raw: str) -> str:
    """Remove accidental markdown code fences from the model response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def generate_report(
    modality: str,
    patient_notes: str | None = None,
    specialist: dict | None = None,
) -> dict:
    """
    Generate a structured diagnostic report using Groq Llama 3.3 70b.

    Args:
        modality:      Canonical imaging modality string.
        patient_notes: Free-text notes entered by the patient at upload time.
        specialist:    Findings dict from the specialist vision model, or None.

    Returns:
        Parsed report dict on success, empty dict on any failure.
    """
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not configured — skipping report generation")
        return {}

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": _build_user_message(modality, patient_notes, specialist),
                },
            ],
            temperature=0.2,
            max_tokens=1200,
        )

        raw = response.choices[0].message.content
        report = json.loads(_strip_fences(raw))
        logger.info(
            "Groq report generated — modality: %s | urgency: %s | confidence: %.0f%%",
            modality,
            report.get("urgency", "unknown"),
            float(report.get("confidence", 0)) * 100,
        )
        return report

    except json.JSONDecodeError:
        logger.exception("Groq returned non-JSON response for modality %s", modality)
        return {}
    except Exception:
        logger.exception("Groq report generation failed for modality %s", modality)
        return {}
