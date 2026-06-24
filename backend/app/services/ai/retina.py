"""RETFound (DINOv2) — local retinal fundus disease detection.

Model: YukunZhou/RETFound_dinov2_meh (public HuggingFace Hub)
Architecture: ViT-L/16 pretrained with DINOv2 SSL on MEH fundus data.
  patch_size=16, hidden=1024, heads=16, layers=24, global_pool=avg.

IMPORTANT — backbone vs fine-tuned:
  The HF checkpoint is the pretrained backbone (fine_tuned=false in config.json).
  It has no classification head, so inference returns None until a downstream
  fine-tuned checkpoint is provided. Fine-tune with the official script:
    torchrun main_finetune.py --model RETFound_dinov2 --adaptation finetune ...
  Then set RETFOUND_FINETUNED_PATH to the resulting checkpoint-best.pth.

Preprocessing pipeline (official RETFound eval + fundus-specific steps):
  1. Circular FOV crop  — removes black border produced by fundus cameras
  2. Square crop        — model expects square input before transform
  3. Ben Graham norm    — removes illumination gradient (highest-impact step)
  4. CLAHE              — enhances microaneurysms, vessels, haemorrhages
  5. Resize 256 → CenterCrop 224 → ToTensor → ImageNet normalise
     (RETFound uses ImageNet mean/std, NOT retinal-specific stats)
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)

_HF_REPO = "YukunZhou/RETFound_dinov2_meh"
_HF_FILENAME = "RETFound_dinov2_meh.pth"
_CACHE_DIR = "/tmp/retfound"  # nosec B108

# EYEPACS / APTOS 5-class DR grading convention
_CLASS_LABELS = ["No DR", "Mild DR", "Moderate DR", "Severe DR", "Proliferative DR"]
_CONFIDENCE_THRESHOLD = 0.05


@lru_cache(maxsize=1)
def _load_model():
    """Returns a ready model, or None if the checkpoint has no classification head."""
    import timm
    import torch
    from huggingface_hub import hf_hub_download

    # Prefer a locally fine-tuned checkpoint; fall back to the HF backbone
    finetuned_path = settings.RETFOUND_FINETUNED_PATH
    if finetuned_path:
        logger.info("Loading fine-tuned RETFound checkpoint from %s…", finetuned_path)
        checkpoint_path = finetuned_path
    else:
        logger.info("Downloading RETFound backbone from HuggingFace Hub…")
        checkpoint_path = hf_hub_download(
            repo_id=_HF_REPO,
            filename=_HF_FILENAME,
            cache_dir=_CACHE_DIR,  # nosec B108
            token=settings.HUGGINGFACE_API_KEY or None,
        )

    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state_dict = checkpoint.get("model", checkpoint.get("state_dict", checkpoint))

    # Backbone-only checkpoint: no classification head → outputs are meaningless
    head_weight = state_dict.get("head.weight")
    if head_weight is None or head_weight.shape[0] != len(_CLASS_LABELS):
        logger.warning(
            "RETFound checkpoint has no %d-class classification head "
            "(fine_tuned=false). Set RETFOUND_FINETUNED_PATH to a downstream "
            "fine-tuned checkpoint to enable retinal DR grading.",
            len(_CLASS_LABELS),
        )
        return None

    # ViT-L/16 with global average pooling (matches config.json: patch_size=16)
    model = timm.create_model(
        "vit_large_patch16_224",
        pretrained=False,
        num_classes=len(_CLASS_LABELS),
        global_pool="avg",
    )
    model.load_state_dict(state_dict, strict=False)
    model.eval()
    logger.info("RETFound model ready")
    return model


def _preprocess(image_bytes: bytes):
    """Full preprocessing pipeline before the official RETFound eval transform."""
    import cv2
    import numpy as np
    import torchvision.transforms as T
    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img_np = np.array(img)

    # Step 1: Circular FOV crop — fundus cameras produce a circle on black bg
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        margin = int(min(w, h) * 0.03)
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(img_np.shape[1] - x, w + 2 * margin)
        h = min(img_np.shape[0] - y, h + 2 * margin)
        img_np = img_np[y : y + h, x : x + w]

    # Step 2: Square crop
    h, w = img_np.shape[:2]
    min_dim = min(h, w)
    top = (h - min_dim) // 2
    left = (w - min_dim) // 2
    img_np = img_np[top : top + min_dim, left : left + min_dim]

    # Step 3: Ben Graham normalisation — removes illumination gradient
    img_np = img_np.astype(np.float32)
    gaussian = cv2.GaussianBlur(img_np, (0, 0), sigmaX=30)
    img_np = cv2.addWeighted(img_np, 4, gaussian, -4, 128)
    img_np = np.clip(img_np, 0, 255).astype(np.uint8)

    # Step 4: CLAHE on the L channel (LAB space)
    img_lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    img_lab[:, :, 0] = clahe.apply(img_lab[:, :, 0])
    img_np = cv2.cvtColor(img_lab, cv2.COLOR_LAB2RGB)

    # Step 5: Official RETFound eval transform — ImageNet stats, BICUBIC interpolation
    eval_transform = T.Compose(
        [
            T.Resize(256, interpolation=T.InterpolationMode.BICUBIC),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    return eval_transform(Image.fromarray(img_np)).unsqueeze(0)  # [1, 3, 224, 224]


def _sync_analyze(image_bytes: bytes) -> dict | None:
    import torch

    try:
        model = _load_model()
    except Exception as exc:
        logger.warning("RETFound not available: %s", exc)
        return None

    if model is None:
        return None  # backbone-only checkpoint, no DR grading possible

    tensor = _preprocess(image_bytes)

    with torch.no_grad():
        logits = model(tensor)[0]  # [num_classes]
        probs = torch.softmax(logits, dim=0).tolist()

    all_findings = {
        label: round(prob, 4)
        for label, prob in zip(_CLASS_LABELS, probs)
        if prob >= _CONFIDENCE_THRESHOLD
    }

    if not all_findings:
        top_idx = max(range(len(probs)), key=lambda i: probs[i])
        all_findings = {_CLASS_LABELS[top_idx]: round(probs[top_idx], 4)}

    top_finding = max(all_findings, key=all_findings.get)

    return {
        "model": "RETFound-dinov2-meh",
        "top_finding": top_finding,
        "top_confidence": all_findings[top_finding],
        "all_findings": all_findings,
    }


async def analyze(image_bytes: bytes) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_analyze, image_bytes)
