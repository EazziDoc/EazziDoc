"""Gemini 2.0 Flash — vision-based modality detection and report generation."""

import base64
import json
import logging

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODALITIES = ["chest_xray", "fundus", "skin", "brain_mri", "mammography", "unknown"]

_MODALITY_PROMPT = """\
You are a radiologist's assistant. Look at this medical image and identify its modality.
Reply with ONLY one of these exact strings (no explanation):
chest_xray, fundus, skin, brain_mri, mammography, unknown
"""

_REPORT_PROMPT = """\
You are a board-certified radiologist AI assistant. Analyse the provided medical image(s) \
and produce a structured diagnostic report as valid JSON.

Return ONLY the JSON object below — no markdown fences, no extra text:
{{
  "summary": "<1-2 sentence overview>",
  "findings": ["<finding 1>", "<finding 2>"],
  "impression": "<primary clinical impression>",
  "differential_diagnoses": ["<dx 1>", "<dx 2>"],
  "recommendations": ["<action 1>", "<action 2>"],
  "urgency": "<routine|urgent|emergent>",
  "confidence": <0.0-1.0>
}}

Patient notes (if any): {patient_notes}
Image modality: {modality}
{specialist_section}"""


def _configure() -> genai.GenerativeModel:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    return genai.GenerativeModel("gemini-2.0-flash")


def _image_part(image_bytes: bytes, content_type: str) -> dict:
    return {
        "inline_data": {
            "mime_type": content_type,
            "data": base64.b64encode(image_bytes).decode(),
        }
    }


def detect_modality(images: list[tuple[bytes, str]]) -> str:
    """Return the medical image modality string for the first image."""
    if not settings.GOOGLE_API_KEY:
        return "unknown"
    try:
        model = _configure()
        parts = [_MODALITY_PROMPT] + [_image_part(b, ct) for b, ct in images[:1]]
        response = model.generate_content(parts)
        result = response.text.strip().lower()
        return result if result in _MODALITIES else "unknown"
    except Exception:
        logger.exception("Gemini modality detection failed")
        return "unknown"


def _format_specialist(specialist: dict | None) -> str:
    if not specialist:
        return "Specialist model: not available for this modality — rely on visual analysis only."
    top = specialist["top_finding"]
    conf = specialist["top_confidence"]
    detail = ", ".join(f"{k} {v:.0%}" for k, v in specialist["all_findings"].items())
    return (
        f"Specialist model ({specialist['model']}) findings — ground your report on these:\n"
        f"Top finding: {top} ({conf:.0%} confidence)\n"
        f"All flagged findings: {detail}"
    )


def generate_report(
    images: list[tuple[bytes, str]],
    modality: str,
    patient_notes: str | None = None,
    specialist: dict | None = None,
) -> dict:
    """Generate a structured diagnostic report. Returns {} on failure."""
    if not settings.GOOGLE_API_KEY:
        return {}
    try:
        model = _configure()
        prompt = _REPORT_PROMPT.format(
            modality=modality,
            patient_notes=patient_notes or "None provided",
            specialist_section=_format_specialist(specialist),
        )
        parts = [prompt] + [_image_part(b, ct) for b, ct in images]
        response = model.generate_content(parts)
        raw = response.text.strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        logger.exception("Gemini report generation failed")
        return {}
