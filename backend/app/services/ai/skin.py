"""Skin disease classifier — local ViT-B/16 inference.

Model: Anwarkh1/Skin_Cancer-Image_Classification (HuggingFace Hub, public)
Architecture: google/vit-base-patch16-224-in21k fine-tuned on HAM10000.
  hidden_size=768, layers=12, heads=12, patch_size=16, image_size=224.

7 classes (id2label order from config.json):
  0: benign_keratosis-like_lesions
  1: basal_cell_carcinoma
  2: actinic_keratoses
  3: vascular_lesions
  4: melanocytic_Nevi
  5: melanoma
  6: dermatofibroma

Preprocessing — ViT-B/16 specific (do NOT use ImageNet stats):
  Google's ViT normalises with mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]
  (maps pixel values to [-1, 1]).
  AutoImageProcessor reads the exact stats from the model's
  preprocessor_config.json — no hardcoding needed.
  Steps: RGB → resize 224×224 → normalise with ViT stats.
  No FOV crop, no Ben Graham, no CLAHE — those are fundus-specific.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL_REPO = "Anwarkh1/Skin_Cancer-Image_Classification"
_CACHE_DIR = "/tmp/skin_model"  # nosec B108
_CONFIDENCE_THRESHOLD = 0.05


@lru_cache(maxsize=1)
def _load_model():
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    logger.info("Loading skin disease classifier from HuggingFace Hub…")
    processor = AutoImageProcessor.from_pretrained(
        _MODEL_REPO,
        cache_dir=_CACHE_DIR,  # nosec B108
        token=settings.HUGGINGFACE_API_KEY or None,
    )
    model = AutoModelForImageClassification.from_pretrained(
        _MODEL_REPO,
        cache_dir=_CACHE_DIR,  # nosec B108
        token=settings.HUGGINGFACE_API_KEY or None,
    )
    model.eval()
    logger.info(
        "Skin model ready — %d classes: %s",
        model.config.num_labels,
        list(model.config.id2label.values()),
    )
    return model, processor


def _preprocess(image_bytes: bytes, processor):
    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    # AutoImageProcessor applies resize + ViT normalisation
    # (mean/std read from preprocessor_config.json — mean=0.5, std=0.5)
    return processor(images=img, return_tensors="pt")["pixel_values"]


def _sync_analyze(image_bytes: bytes) -> dict | None:
    import torch

    try:
        model, processor = _load_model()
    except Exception as exc:
        logger.warning("Skin model unavailable: %s", exc)
        return None

    pixel_values = _preprocess(image_bytes, processor)

    with torch.no_grad():
        logits = model(pixel_values=pixel_values).logits[0]
        probs = torch.softmax(logits, dim=0).tolist()

    # Labels sourced from model.config.id2label — matches config.json exactly
    labels = [model.config.id2label[i] for i in range(len(probs))]

    all_findings = {
        label: round(prob, 4) for label, prob in zip(labels, probs) if prob >= _CONFIDENCE_THRESHOLD
    }
    if not all_findings:
        top_idx = max(range(len(probs)), key=lambda i: probs[i])
        all_findings = {labels[top_idx]: round(probs[top_idx], 4)}

    top_finding = max(all_findings, key=all_findings.get)

    return {
        "model": "ViT-SkinDisease-HAM10000",
        "top_finding": top_finding,
        "top_confidence": all_findings[top_finding],
        "all_findings": all_findings,
    }


async def analyze(image_bytes: bytes) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_analyze, image_bytes)
