"""MedSAM — medical image segmentation overlay.

Segment Anything Model fine-tuned on medical images. Generates a coloured
segmentation overlay on the primary image and uploads it to R2, storing the
key in the diagnosis report for the frontend to display.

Checkpoint: MedSAM ViT-B (~375 MB)
Downloaded from: https://github.com/bowang-lab/MedSAM (see README for link)

Set MEDSAM_CHECKPOINT_PATH env var to the local path of the checkpoint file.
If not set or the file does not exist, this service is silently skipped —
the rest of the pipeline runs normally without an overlay.

Install: pip install segment-anything
"""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

_OVERLAY_COLOR = (255, 100, 50)  # orange-red overlay
_OVERLAY_ALPHA = 0.45


def _checkpoint_path() -> Path | None:
    path = os.environ.get("MEDSAM_CHECKPOINT_PATH", "")
    if not path:
        return None
    p = Path(path)
    return p if p.exists() else None


@lru_cache(maxsize=1)
def _load_model(checkpoint: str):
    from segment_anything import SamPredictor, sam_model_registry

    logger.info("Loading MedSAM from %s…", checkpoint)
    sam = sam_model_registry["vit_b"](checkpoint=checkpoint)
    sam.eval()
    predictor = SamPredictor(sam)
    logger.info("MedSAM ready")
    return predictor


def _sync_segment(image_bytes: bytes) -> bytes | None:
    """Run MedSAM and return the overlay image as PNG bytes, or None on failure."""
    ckpt = _checkpoint_path()
    if ckpt is None:
        return None

    try:
        import numpy as np
        from PIL import Image

        predictor = _load_model(str(ckpt))

        pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(pil_img)

        predictor.set_image(img_np)

        h, w = img_np.shape[:2]
        # Full-image bounding box — segments the most prominent structure
        box = np.array([0, 0, w, h])

        masks, scores, _ = predictor.predict(
            box=box,
            multimask_output=True,
        )

        # Use the mask with the highest score
        best_mask = masks[scores.argmax()]

        # Build RGBA overlay
        overlay = np.zeros((*img_np.shape[:2], 4), dtype=np.uint8)
        overlay[best_mask] = [*_OVERLAY_COLOR, int(255 * _OVERLAY_ALPHA)]

        base = pil_img.convert("RGBA")
        overlay_img = Image.fromarray(overlay, "RGBA")
        composite = Image.alpha_composite(base, overlay_img).convert("RGB")

        buf = BytesIO()
        composite.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    except Exception:
        logger.exception("MedSAM segmentation failed")
        return None


async def segment_and_upload(
    image_bytes: bytes,
    diagnosis_id: str,
    storage,
) -> str | None:
    """Segment the image and upload the overlay to R2.

    Returns the R2 key of the overlay image, or None if MedSAM is not
    configured or segmentation fails.
    """
    if _checkpoint_path() is None:
        return None

    loop = asyncio.get_event_loop()
    overlay_bytes = await loop.run_in_executor(None, _sync_segment, image_bytes)

    if not overlay_bytes:
        return None

    key = f"diagnoses/{diagnosis_id}/seg_overlay.png"
    try:
        await storage.upload(overlay_bytes, key, "image/png")
        logger.info("MedSAM overlay uploaded → %s", key)
        return key
    except Exception:
        logger.exception("Failed to upload MedSAM overlay for diagnosis %s", diagnosis_id)
        return None
