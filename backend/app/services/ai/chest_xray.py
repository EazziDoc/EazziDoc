"""TorchXRayVision — chest X-ray pathology classification.

Runs in-process on CPU (~3-5s). Model weights (~30 MB) are downloaded on
first call and cached by torchxrayvision automatically.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from io import BytesIO

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.15  # only report pathologies above this score


@lru_cache(maxsize=1)
def _load_model():
    """Load once, reuse across requests. Thread-safe via GIL for CPU inference."""
    import torchxrayvision as xrv

    logger.info("Loading TorchXRayVision model (first call — downloads weights if needed)…")
    model = xrv.models.DenseNet(weights="densenet121-res224-all")
    model.eval()
    logger.info("TorchXRayVision model ready")
    return model


def _sync_analyze(image_bytes: bytes) -> dict:
    import skimage.io
    import skimage.transform
    import torch
    import torchxrayvision as xrv

    model = _load_model()

    img = skimage.io.imread(BytesIO(image_bytes), as_gray=True)
    img = xrv.datasets.normalize(img, 255)

    if img.ndim == 3:
        img = img.mean(axis=2)

    img = skimage.transform.resize(img, (224, 224), anti_aliasing=True)
    img = img[None, None, ...]  # [1, 1, H, W]
    img_tensor = torch.from_numpy(img).float()

    with torch.no_grad():
        preds = model(img_tensor)[0].tolist()

    all_findings = {
        pathology: round(score, 4)
        for pathology, score in zip(model.pathologies, preds)
        if score >= _CONFIDENCE_THRESHOLD
    }

    if not all_findings:
        no_finding_idx = model.pathologies.index("No Finding")
        all_findings = {"No Finding": round(preds[no_finding_idx], 4)}

    top_finding = max(all_findings, key=all_findings.get)

    return {
        "model": "torchxrayvision-densenet121-all",
        "top_finding": top_finding,
        "top_confidence": all_findings[top_finding],
        "all_findings": all_findings,
    }


async def analyze(image_bytes: bytes) -> dict:
    """Run TorchXRayVision in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_analyze, image_bytes)
