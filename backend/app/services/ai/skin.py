"""Skin disease classifier — HuggingFace Inference API.

Model: Anwarkh1/Skin_Cancer-Image_Classification
Architecture: ViT-B/16 fine-tuned on HAM10000 (7 classes).

Using the HF Inference API instead of loading the model locally removes the
need for the `transformers` package (~600 MB) from the worker image and
avoids loading ~400 MB of weights into RAM per worker process.

7 classes:
  benign_keratosis-like_lesions, basal_cell_carcinoma, actinic_keratoses,
  vascular_lesions, melanocytic_Nevi, melanoma, dermatofibroma
"""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL_REPO = "Anwarkh1/Skin_Cancer-Image_Classification"
_API_URL = f"https://router.huggingface.co/hf-inference/models/{_MODEL_REPO}"
_CONFIDENCE_THRESHOLD = 0.05


def _sync_analyze(image_bytes: bytes) -> dict | None:
    if not settings.HUGGINGFACE_API_KEY:
        logger.warning("HUGGINGFACE_API_KEY not set — skin model unavailable")
        return None

    try:
        import httpx
        from PIL import Image

        # Normalise to JPEG so the request always carries a known content type.
        buf = BytesIO()
        Image.open(BytesIO(image_bytes)).convert("RGB").save(buf, format="JPEG", quality=95)
        jpeg_bytes = buf.getvalue()

        resp = httpx.post(
            _API_URL,
            content=jpeg_bytes,
            headers={
                "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
                "Content-Type": "image/jpeg",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        results = resp.json()  # [{"label": str, "score": float}, ...]

        all_findings = {
            r["label"]: round(r["score"], 4) for r in results if r["score"] >= _CONFIDENCE_THRESHOLD
        }
        if not all_findings:
            top = max(results, key=lambda r: r["score"])
            all_findings = {top["label"]: round(top["score"], 4)}

        top_finding = max(all_findings, key=all_findings.get)

        logger.info(
            "Skin API → top: %s (%.0f%%)",
            top_finding,
            all_findings[top_finding] * 100,
        )
        return {
            "model": "ViT-SkinDisease-HAM10000",
            "top_finding": top_finding,
            "top_confidence": all_findings[top_finding],
            "all_findings": all_findings,
        }

    except Exception as exc:
        logger.warning("Skin HF Inference API failed: %s", exc)
        return None


async def analyze(image_bytes: bytes) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_analyze, image_bytes)
