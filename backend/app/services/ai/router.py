"""Modality → specialist model dispatcher.

Each specialist runs in-process (CPU) or via HF Inference API and returns
a standardised findings dict. Failures are caught and logged — the main
Gemini pipeline always continues, just without specialist grounding.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SUPPORTED = {"chest_xray", "fundus", "skin"}


async def run_specialist(image_bytes: bytes, modality: str) -> dict | None:
    """Dispatch to the correct specialist model for *modality*.

    Returns a findings dict on success, None if the modality has no
    specialist or the specialist fails.
    """
    if modality not in _SUPPORTED:
        return None

    try:
        if modality == "chest_xray":
            from app.services.ai.chest_xray import analyze
        elif modality == "fundus":
            from app.services.ai.retina import analyze
        else:
            from app.services.ai.skin import analyze

        result = await analyze(image_bytes)
        if result is None:
            logger.warning("Specialist (%s) returned None — continuing without", modality)
            return None
        logger.info(
            "Specialist (%s) → top: %s (%.0f%%)",
            modality,
            result.get("top_finding"),
            (result.get("top_confidence", 0)) * 100,
        )
        return result
    except Exception:
        logger.exception("Specialist model failed for modality %s — continuing without", modality)
        return None
