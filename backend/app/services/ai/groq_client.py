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
) -> dict:
    """Text-only fallback when Gemini vision is unavailable. Returns {} on failure."""
    if not settings.GROQ_API_KEY:
        return {}
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        user_msg = (
            f"Modality: {modality}\n"
            f"Patient notes: {patient_notes or 'None provided'}\n\n"
            "Generate a diagnostic report based on the modality and patient notes alone."
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
