"""Groq Llama 3.3 70b — text-only fallback report generator."""

import json
import logging

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a board-certified radiologist AI assistant. Produce a structured \
diagnostic report as valid JSON with these exact keys:
summary, findings (list), impression, differential_diagnoses (list),
recommendations (list), urgency (routine|urgent|emergent), confidence (0.0-1.0).
Return ONLY the JSON object — no markdown, no explanation.
"""


def generate_report(
    modality: str,
    patient_notes: str | None = None,
    specialist: dict | None = None,
) -> dict:
    """Text-only fallback when Gemini vision is unavailable. Returns {} on failure."""
    if not settings.GROQ_API_KEY:
        return {}
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        specialist_section = ""
        if specialist:
            top = specialist["top_finding"]
            conf = specialist["top_confidence"]
            detail = ", ".join(f"{k} {v:.0%}" for k, v in specialist["all_findings"].items())
            specialist_section = (
                f"\nSpecialist model ({specialist['model']}) findings:\n"
                f"Top: {top} ({conf:.0%}). All: {detail}\n"
                "Ground your report on these findings."
            )
        user_msg = (
            f"Modality: {modality}\n"
            f"Patient notes: {patient_notes or 'None provided'}\n"
            f"{specialist_section}\n"
            "Generate a diagnostic report based on the above information."
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        logger.exception("Groq fallback report generation failed")
        return {}
