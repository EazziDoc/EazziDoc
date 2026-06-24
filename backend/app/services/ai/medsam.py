"""LiteMedSAM — medical image segmentation overlay.

LiteMedSAM (CVPR 2024) — 10× faster than standard MedSAM, TinyViT backbone.
Generates a coloured segmentation overlay on the primary image and uploads
it to R2, storing the key in the diagnosis report for the frontend.

Checkpoint: lite_medsam.pth (~30 MB)
  1. Download from Google Drive (link in bowang-lab/MedSAM README, LiteMedSAM branch)
  2. Upload to your R2 bucket:
       aws s3 cp lite_medsam.pth s3://<bucket>/models/lite_medsam.pth \\
         --endpoint-url https://<account-id>.r2.cloudflarestorage.com
  3. Set the Fly secret:  fly secrets set MEDSAM_R2_KEY=models/lite_medsam.pth
  The worker downloads the checkpoint to /tmp on first use and caches it in
  memory for the lifetime of the process. Leave MEDSAM_R2_KEY unset to
  disable the overlay without affecting the rest of the pipeline.

Dependency: install from the LiteMedSAM branch (registers vit_t):
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
from functools import lru_cache
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCAL_CACHE = Path("/tmp/litemedsam/lite_medsam.pth")  # nosec B108

_OVERLAY_ALPHA = 0.40

_MODALITY_COLORS: dict[str, tuple[int, int, int]] = {
    "chest_xray": (100, 180, 255),  # cool blue   — lung fields
    "fundus": (80, 220, 120),  # green       — retinal structures
    "skin": (255, 100, 50),  # orange-red  — lesion boundary
    "brain_mri": (200, 80, 255),  # purple      — focal lesion
    "mammography": (255, 210, 60),  # amber       — mass / calcification
}
_DEFAULT_COLOR = (255, 100, 50)  # orange-red fallback


def _ensure_checkpoint() -> Path | None:
    """Return the local checkpoint path, downloading from R2 if not cached."""
    from app.core.config import settings

    if not settings.MEDSAM_R2_KEY:
        return None

    if _LOCAL_CACHE.exists():
        return _LOCAL_CACHE

    try:
        import boto3

        _LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)  # nosec B108
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        logger.info("Downloading LiteMedSAM checkpoint from R2 (%s)…", settings.MEDSAM_R2_KEY)
        s3.download_file(
            settings.CLOUDFLARE_R2_BUCKET_NAME, settings.MEDSAM_R2_KEY, str(_LOCAL_CACHE)
        )
        logger.info("LiteMedSAM checkpoint ready at %s", _LOCAL_CACHE)
        return _LOCAL_CACHE
    except Exception:
        logger.exception("Failed to download LiteMedSAM checkpoint from R2")
        return None


@lru_cache(maxsize=1)
def _load_model(checkpoint: str):
    try:
        from segment_anything import SamPredictor, sam_model_registry
    except ImportError:
        logger.warning("segment_anything not installed — LiteMedSAM disabled")
        return None

    if "vit_t" not in sam_model_registry:
        logger.warning(
            "sam_model_registry has no 'vit_t' key — the standard PyPI segment-anything "
            "is installed instead of the LiteMedSAM fork. "
            "Rebuild the worker image with --local-only to enable segmentation overlays."
        )
        return None

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
    ckpt = _ensure_checkpoint()
    if ckpt is None:
        return None

    try:
        import numpy as np
        from PIL import Image, ImageFilter

        predictor = _load_model(str(ckpt))
        if predictor is None:
            return None

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
        logger.exception("LiteMedSAM segmentation failed")
        return None


async def segment_and_upload(
    image_bytes: bytes,
    diagnosis_id: str,
    storage,
    modality: str | None = None,
) -> str | None:
    """Segment the primary image and upload the coloured overlay to R2.

    Returns the R2 object key on success, or None if LiteMedSAM is not
    configured or segmentation fails. The rest of the pipeline is unaffected.
    """
    from app.core.config import settings

    if not settings.MEDSAM_R2_KEY:
        return None

    loop = asyncio.get_event_loop()
    overlay_bytes = await loop.run_in_executor(None, _sync_segment, image_bytes, modality)

    if not overlay_bytes:
        return None

    key = f"diagnoses/{diagnosis_id}/seg_overlay.png"
    try:
        await storage.upload(overlay_bytes, key, "image/png")
        logger.info("LiteMedSAM overlay uploaded → %s", key)
        return key
    except Exception:
        logger.exception("Failed to upload LiteMedSAM overlay for diagnosis %s", diagnosis_id)
        return None
