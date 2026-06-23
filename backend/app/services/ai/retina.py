"""RETFound — retinal disease detection via HuggingFace free Inference API.

Makes an async HTTP call to the HF serverless endpoint. The free tier has:
- ~1000 calls/day
- Cold start: 20-40s (model loads on first request after idle)
- Subsequent calls: 2-5s

Failures are logged and return None — the pipeline continues without
retinal specialist grounding in that case.

License: RETFound is CC-BY-NC 4.0 (non-commercial). Appropriate for demo
and research use. Obtain a commercial license before billing patients for
retinal analysis.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_HF_MODEL = "rmaphoh/RETFound_cfp"
_API_URL = f"https://api-inference.huggingface.co/models/{_HF_MODEL}"
_TIMEOUT = 90.0  # cold starts on free tier can take 40s


async def analyze(image_bytes: bytes) -> dict | None:
    """Call RETFound via HuggingFace free Inference API.

    Returns a findings dict or None on any failure (network, cold-start
    timeout, model not ready). Caller continues gracefully in both cases.
    """
    if not settings.HUGGINGFACE_API_KEY:
        logger.warning("HUGGINGFACE_API_KEY not set — skipping RETFound")
        return None

    import httpx

    headers = {
        "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
        "Content-Type": "application/octet-stream",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_API_URL, headers=headers, content=image_bytes)
            resp.raise_for_status()
            data = resp.json()

        # Standard HF image-classification response
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
                "model": "RETFound-cfp",
                "top_finding": top,
                "top_confidence": all_findings[top],
                "all_findings": all_findings,
            }

        # HF cold-start: {"error": "Model ... is currently loading", "estimated_time": 30}
        if isinstance(data, dict) and "error" in data:
            logger.warning("RETFound cold start / not ready: %s", data.get("error"))
            return None

        return None

    except httpx.TimeoutException:
        logger.warning("RETFound HF API timed out after %.0fs — continuing without", _TIMEOUT)
        return None
    except Exception:
        logger.exception("RETFound HF API call failed — continuing without retinal specialist")
        return None
