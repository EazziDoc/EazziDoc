"""LiteMedSAM — medical image segmentation overlay.

LiteMedSAM (CVPR 2024) — 10× faster than standard MedSAM, TinyViT backbone.
Generates a coloured segmentation overlay on the primary image and uploads
it to R2, storing the key in the diagnosis report for the frontend.

Checkpoint: lite_medsam.pth (~30 MB)
  Download from Google Drive link in:
  https://github.com/bowang-lab/MedSAM/tree/LiteMedSAM
  Set MEDSAM_CHECKPOINT_PATH env var to the absolute path of the .pth file.
  If not set or the file does not exist this service silently skips —
  the rest of the pipeline continues normally without an overlay.

Dependency: install from the LiteMedSAM branch (registers vit_t in the
  segment_anything registry):
    git clone -b LiteMedSAM https://github.com/bowang-lab/MedSAM
    pip install -e ./MedSAM

Modality-aware behaviour:
  - Grayscale modalities (chest_xray, brain_mri, mammography) are stacked to
    3-channel RGB before being passed to the SAM image encoder.
  - The bounding-box prompt covers the central 90 % of the image to avoid
    scanner borders, annotation text, and edge artefacts.
  - Overlay colour is chosen per modality for easier interpretation.
  - A solid 2-px outline is drawn around the mask boundary so the overlay
    is visible even on dark backgrounds.
"""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

_OVERLAY_ALPHA = 0.40

_MODALITY_COLORS: dict[str, tuple[int, int, int]] = {
    "chest_xray": (100, 180, 255),  # cool blue   — lung fields
    "fundus": (80, 220, 120),  # green       — retinal structures
    "skin": (255, 100, 50),  # orange-red  — lesion boundary
    "brain_mri": (200, 80, 255),  # purple      — focal lesion
    "mammography": (255, 210, 60),  # amber       — mass / calcification
}
_DEFAULT_COLOR = (255, 100, 50)  # orange-red fallback


def _checkpoint_path() -> Path | None:
    path = os.environ.get("MEDSAM_CHECKPOINT_PATH", "")
    if not path:
        return None
    p = Path(path)
    return p if p.exists() else None


@lru_cache(maxsize=1)
def _load_model(checkpoint: str):
    from segment_anything import SamPredictor, sam_model_registry

    logger.info("Loading LiteMedSAM from %s…", checkpoint)
    sam = sam_model_registry["vit_t"](checkpoint=checkpoint)
    sam.eval()
    predictor = SamPredictor(sam)
    logger.info("LiteMedSAM ready")
    return predictor


def _to_rgb(image_bytes: bytes) -> np.ndarray:
    """Convert any medical image to a uint8 [H, W, 3] RGB array.

    Grayscale images (chest X-ray, brain MRI, mammography exported as L/I/F)
    are stacked to 3-channel RGB so the SAM image encoder can process them
    without modification.
    """
    import numpy as np
    from PIL import Image

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("L", "I", "F"):
        arr = np.array(img.convert("L"), dtype=np.uint8)
        return np.stack([arr, arr, arr], axis=2)
    return np.array(img.convert("RGB"), dtype=np.uint8)


def _center_box(h: int, w: int, margin: float = 0.05) -> np.ndarray:
    """Bounding box covering the central (1 − 2·margin) fraction of the image.

    Using the full image [0, 0, w, h] includes scanner borders and annotation
    artefacts. A 5 % margin focuses the prompt on the clinical content.
    """
    import numpy as np

    return np.array(
        [
            int(w * margin),
            int(h * margin),
            int(w * (1.0 - margin)),
            int(h * (1.0 - margin)),
        ]
    )


def _sync_segment(image_bytes: bytes, modality: str | None) -> bytes | None:
    ckpt = _checkpoint_path()
    if ckpt is None:
        return None

    try:
        import numpy as np
        from PIL import Image, ImageFilter

        predictor = _load_model(str(ckpt))
        img_np = _to_rgb(image_bytes)
        h, w = img_np.shape[:2]

        predictor.set_image(img_np)

        box = _center_box(h, w, margin=0.05)
        masks, scores, _ = predictor.predict(box=box, multimask_output=True)
        best_mask = masks[scores.argmax()]

        color = _MODALITY_COLORS.get(modality or "", _DEFAULT_COLOR)

        # Semi-transparent fill over the segmented region
        overlay = np.zeros((*img_np.shape[:2], 4), dtype=np.uint8)
        overlay[best_mask] = [*color, int(255 * _OVERLAY_ALPHA)]

        # Solid 2-px outline — FIND_EDGES on the binary mask gives a clean border
        mask_pil = Image.fromarray((best_mask * 255).astype(np.uint8), mode="L")
        edge_arr = np.array(mask_pil.filter(ImageFilter.FIND_EDGES)) > 0
        overlay[edge_arr] = [*color, 255]

        base = Image.fromarray(img_np).convert("RGBA")
        composite = Image.alpha_composite(base, Image.fromarray(overlay, "RGBA")).convert("RGB")

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
    modality: str | None = None,
) -> str | None:
    """Segment the primary image and upload the coloured overlay to R2.

    Returns the R2 object key on success, or None if MedSAM is not configured
    or segmentation fails. The rest of the pipeline is unaffected.
    """
    if _checkpoint_path() is None:
        return None

    loop = asyncio.get_event_loop()
    overlay_bytes = await loop.run_in_executor(None, _sync_segment, image_bytes, modality)

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
