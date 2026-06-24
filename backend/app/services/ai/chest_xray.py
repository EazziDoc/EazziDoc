"""TorchXRayVision — chest X-ray pathology classification.

Runs in-process on CPU (~3-5s). Model weights are downloaded on first call
and cached to /tmp/torchxrayvision (writable in containerised environments).

Preprocessing rules (from TorchXRayVision docs and training pipeline):
  - Read as raw uint8 so normalize(img, 255) maps [0,255] → [-1024,1024]
  - Stay grayscale; never average after normalizing (would corrupt HU values)
  - Use XRayCenterCrop + XRayResizer, not a naive resize (preserves lung field)
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from io import BytesIO

import numpy as np

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.15


@lru_cache(maxsize=1)
def _load_model():
    import torchxrayvision as xrv

    logger.info("Loading TorchXRayVision model (first call — downloads weights if needed)…")
    model = xrv.models.DenseNet(weights="densenet121-res224-all", cache_dir="/tmp/torchxrayvision")  # nosec B108
    model.eval()
    logger.info("TorchXRayVision model ready")
    return model


def _sync_analyze(image_bytes: bytes) -> dict:
    import skimage.io
    import torch
    import torchxrayvision as xrv

    model = _load_model()

    # Read as raw uint8 — as_gray=True returns [0,1] float which breaks normalize(img, 255)
    img = skimage.io.imread(BytesIO(image_bytes))

    # Drop alpha channel before any processing
    if img.ndim == 3 and img.shape[2] == 4:
        img = img[:, :, :3]

    # Rule 2: XRV normalize maps [0, 255] → [-1024, 1024]
    img = xrv.datasets.normalize(img, 255)

    # Rule 1: Collapse RGB to single grayscale channel AFTER normalize
    if img.ndim == 3:
        img = img.mean(axis=2)  # [H, W]

    # Add channel dim for XRV transforms: [1, H, W]
    img = img[np.newaxis, :]

    # Rule 3: Centre-crop to square then resize — preserves lung field proportions
    img = xrv.datasets.XRayCenterCrop()(img)  # [1, min(H,W), min(H,W)]
    img = xrv.datasets.XRayResizer(224)(img)  # [1, 224, 224]

    img_tensor = torch.from_numpy(img).float().unsqueeze(0)  # [1, 1, 224, 224]

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
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_analyze, image_bytes)
