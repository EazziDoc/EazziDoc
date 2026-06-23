"""Skin disease classifier via HuggingFace free Inference API.

Calls a HAM10000-trained model hosted on HuggingFace — no local model
weights, no in-process GPU/CPU memory. Same free-tier approach as RETFound.

Default model: Anwarkh1/Skin_Disease-Image_Classification
Override via SKIN_MODEL_ID env var to swap to a better model without code changes.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "Anwarkh1/Skin_Disease-Image_Classification"
_TIMEOUT = 60.0


def _model_id() -> str:
    return getattr(settings, "SKIN_MODEL_ID", None) or _DEFAULT_MODEL


async def analyze(image_bytes: bytes) -> dict | None:
    """Call the skin classifier via HuggingFace free Inference API.

    Returns a findings dict or None on failure (cold start, rate limit, etc.).
    """
    if not settings.HUGGINGFACE_API_KEY:
        logger.warning("HUGGINGFACE_API_KEY not set — skipping skin classifier")
        return None

    import httpx

    model = _model_id()
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
        "Content-Type": "application/octet-stream",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, content=image_bytes)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list) and data:
            all_findings = {
                item["label"]: round(item["score"], 4)
                for item in data
                if item.get("score", 0) >= 0.05
            }
            if not all_findings:
                top_raw = max(data, key=lambda x: x.get("score", 0))
                all_findings = {top_raw["label"]: round(top_raw["score"], 4)}

            top = max(all_findings, key=all_findings.get)
            return {
                "model": model.split("/")[-1],
                "top_finding": top,
                "top_confidence": all_findings[top],
                "all_findings": all_findings,
            }

        if isinstance(data, dict) and "error" in data:
            logger.warning("Skin model not ready (cold start): %s", data.get("error"))
            return None

        return None

    except httpx.TimeoutException:
        logger.warning("Skin HF API timed out — continuing without")
        return None
    except Exception:
        logger.exception("Skin HF API call failed — continuing without skin specialist")
        return None
