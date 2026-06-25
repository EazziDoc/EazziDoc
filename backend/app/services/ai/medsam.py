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

Dependency: standard PyPI segment_anything + local tiny_vit_sam.py.
  MedSAM_Lite is constructed directly from TinyViT + PromptEncoder +
  MaskDecoder — sam_model_registry is NOT used. This avoids the
  vit_t registration that only exists in the LiteMedSAM fork.

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
    """Build and load MedSAM_Lite directly from TinyViT + SAM components.

    Does NOT use sam_model_registry["vit_t"]. The standard PyPI
    segment_anything package is sufficient — only MaskDecoder, PromptEncoder,
    and TwoWayTransformer are needed from it. TinyViT is imported from the
    local tiny_vit_sam.py (shipped with the repo).
    """
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from segment_anything.modeling import MaskDecoder, PromptEncoder, TwoWayTransformer

        from app.services.ai.tiny_vit_sam import TinyViT
    except ImportError as e:
        logger.warning("LiteMedSAM dependencies not available — segmentation disabled: %s", e)
        return None

    class MedSAM_Lite(nn.Module):
        def __init__(self, image_encoder, mask_decoder, prompt_encoder):
            super().__init__()
            self.image_encoder = image_encoder
            self.mask_decoder = mask_decoder
            self.prompt_encoder = prompt_encoder

        def forward(self, image, box_np):
            image_embedding = self.image_encoder(image)
            with torch.no_grad():
                box_torch = torch.as_tensor(box_np, dtype=torch.float32, device=image.device)
                if len(box_torch.shape) == 2:
                    box_torch = box_torch[:, None, :]
            sparse_embeddings, dense_embeddings = self.prompt_encoder(
                points=None,
                boxes=box_torch,
                masks=None,
            )
            low_res_masks, _ = self.mask_decoder(
                image_embeddings=image_embedding,
                image_pe=self.prompt_encoder.get_dense_pe(),
                sparse_prompt_embeddings=sparse_embeddings,
                dense_prompt_embeddings=dense_embeddings,
                multimask_output=False,
            )
            return low_res_masks

        @torch.no_grad()
        def postprocess_masks(self, masks, new_size, original_size):
            masks = masks[..., : new_size[0], : new_size[1]]
            masks = F.interpolate(
                masks,
                size=(original_size[0], original_size[1]),
                mode="bilinear",
                align_corners=False,
            )
            return masks

    try:
        image_encoder = TinyViT(
            img_size=256,
            in_chans=3,
            embed_dims=[64, 128, 160, 320],
            depths=[2, 2, 6, 2],
            num_heads=[2, 4, 5, 10],
            window_sizes=[7, 7, 14, 7],
            mlp_ratio=4.0,
            drop_rate=0.0,
            drop_path_rate=0.0,
            use_checkpoint=False,
            mbconv_expand_ratio=4.0,
            local_conv_size=3,
            layer_lr_decay=0.8,
        )
        prompt_encoder = PromptEncoder(
            embed_dim=256,
            image_embedding_size=(64, 64),
            input_image_size=(256, 256),
            mask_in_chans=16,
        )
        mask_decoder = MaskDecoder(
            num_multimask_outputs=3,
            transformer=TwoWayTransformer(
                depth=2,
                embedding_dim=256,
                mlp_dim=2048,
                num_heads=8,
            ),
            transformer_dim=256,
            iou_head_depth=3,
            iou_head_hidden_dim=256,
        )
        model = MedSAM_Lite(
            image_encoder=image_encoder,
            mask_decoder=mask_decoder,
            prompt_encoder=prompt_encoder,
        )
        # lite_medsam.pth is a state dict from a trusted source
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)  # nosec B614
        model.load_state_dict(ckpt)
        model.eval()
        logger.info("LiteMedSAM ready (TinyViT backbone, checkpoint=%s)", checkpoint)
        return model
    except Exception:
        logger.exception("Failed to load LiteMedSAM model")
        return None


def _to_rgb(image_bytes: bytes):
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


def _sync_segment(image_bytes: bytes, modality: str | None) -> bytes | None:
    ckpt = _ensure_checkpoint()
    if ckpt is None:
        return None

    try:
        import cv2
        import numpy as np
        import torch
        from PIL import Image, ImageFilter

        model = _load_model(str(ckpt))
        if model is None:
            return None

        img_np = _to_rgb(image_bytes)
        H, W = img_np.shape[:2]

        # Resize longest side to 256, pad to 256×256 (official LiteMedSAM pipeline)
        scale = 256.0 / max(H, W)
        newh, neww = int(H * scale + 0.5), int(W * scale + 0.5)
        img_256 = cv2.resize(img_np, (neww, newh), interpolation=cv2.INTER_AREA)
        img_256_norm = (img_256 - img_256.min()) / max(float(img_256.max() - img_256.min()), 1e-8)
        img_256_padded = np.pad(img_256_norm, ((0, 256 - newh), (0, 256 - neww), (0, 0)))
        img_tensor = torch.tensor(img_256_padded).float().permute(2, 0, 1).unsqueeze(0)

        # Central-90% bounding box at 256 scale
        margin = 0.05
        box256 = np.array(
            [
                [
                    int(256 * margin),
                    int(256 * margin),
                    int(256 * (1 - margin)),
                    int(256 * (1 - margin)),
                ]
            ]
        )

        with torch.no_grad():
            low_res_masks = model(img_tensor, box256)
            masks = model.postprocess_masks(low_res_masks, (newh, neww), (H, W))
            best_mask = (torch.sigmoid(masks[0, 0]) > 0.5).numpy()

        color = _MODALITY_COLORS.get(modality or "", _DEFAULT_COLOR)

        # Semi-transparent fill over segmented region
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
