"""RETFound — two-stage retinal disease detection.

Stage 1 — Broad screening (kaavyap/retinal-disease-retfound):
  8-class ODIR fine-tune: Normal, Diabetes, Glaucoma, Cataract,
  AMD, Hypertension, Myopia, Other.

Stage 2 — DR-grading cascade (bswift/RETfound_eyepacs_DR):
  Triggered when Stage 1 Diabetes probability >= DR_CASCADE_THRESHOLD.
  5-class EYEPACS fine-tune: No DR, Mild NPDR, Moderate NPDR, Severe NPDR, PDR.
  Class order confirmed from the predictions/ directory in the HF repo.

Both models are RETFound ViT-L/16 fine-tunes and share the same
preprocessing pipeline (fundus-specific steps + ImageNet normalisation).

Preprocessing:
  1. Circular FOV crop  — removes black border from fundus camera
  2. Square crop        — model expects square input
  3. Ben Graham norm    — removes illumination gradient (highest-impact step)
  4. CLAHE              — enhances microaneurysms, vessels, haemorrhages
  5. Resize 256 → CenterCrop 224 → ToTensor → ImageNet normalise
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)

_ODIR_REPO = "kaavyap/retinal-disease-retfound"
_ODIR_FILE = "retfound_odir_best.pth"

_DR_REPO = "bswift/RETfound_eyepacs_DR"
_DR_FILE = "checkpoint-best.pth"

_CACHE_DIR = "/tmp/retfound"  # nosec B108

# Standard ODIR label order (N, D, G, C, A, H, M, O).
# Verify against training code if results look wrong.
_ODIR_LABELS = [
    "Normal",
    "Diabetes",
    "Glaucoma",
    "Cataract",
    "AMD",
    "Hypertension",
    "Myopia",
    "Other",
]

# EYEPACS label order confirmed from predictions/ filenames in bswift repo.
_DR_LABELS = ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "PDR"]

# Diabetes probability at which Stage 2 triggers
_DR_CASCADE_THRESHOLD = 0.35
_CONFIDENCE_THRESHOLD = 0.05


def _load_odir_checkpoint():
    """Download and load kaavyap/retinal-disease-retfound.

    The checkpoint uses a custom architecture:
      - backbone.*  : ViT-L/16, CLS token output (1024-d)
      - head.mlp.*  : MLP(1025→512→8) — 1025 = 1024 backbone + 1 age scalar
    Saved under key 'model_state_dict' (not 'model' or 'state_dict').
    Age is zeroed at inference; the model was trained with age dropout so this
    is equivalent to the training-time drop behaviour.
    """
    import timm
    import torch
    import torch.nn as nn
    from huggingface_hub import hf_hub_download

    class _Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = timm.create_model(
                "vit_large_patch16_224",
                pretrained=False,
                num_classes=0,
                global_pool="token",  # CLS token → 1024-d
            )

            class _Head(nn.Module):
                def __init__(self):
                    super().__init__()
                    # Must be named .mlp so keys match checkpoint: head.mlp.0.*, head.mlp.1.*, etc.
                    self.mlp = nn.Sequential(
                        nn.Linear(1025, 512),  # head.mlp.0
                        nn.LayerNorm(512),  # head.mlp.1 — no running stats, matches checkpoint
                        nn.ReLU(inplace=True),
                        nn.Dropout(0.3),
                        nn.Linear(512, 8),  # head.mlp.4
                    )

                def forward(self, x: torch.Tensor) -> torch.Tensor:
                    return self.mlp(x)

            self.head = _Head()

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            feat = self.backbone(x)  # [B, 1024]
            age = torch.zeros(x.shape[0], 1, dtype=feat.dtype, device=feat.device)
            return self.head(torch.cat([feat, age], dim=1))  # [B, 8]

    path = hf_hub_download(
        repo_id=_ODIR_REPO,
        filename=_ODIR_FILE,
        cache_dir=_CACHE_DIR,  # nosec B108
        token=settings.HUGGINGFACE_API_KEY or None,
    )
    # weights_only=False: checkpoint contains non-tensor objects (argparse.Namespace etc.)
    # blocked by PyTorch 2.6+ default. kaavyap/retinal-disease-retfound is trusted.
    ckpt = torch.load(path, map_location="cpu", weights_only=False)  # nosec B614
    sd = ckpt.get("model_state_dict", ckpt.get("model", ckpt.get("state_dict", ckpt)))

    model = _Model()
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing:
        logger.warning("ODIR checkpoint missing keys: %s", missing)
    if unexpected:
        logger.warning("ODIR checkpoint unexpected keys: %s", unexpected)
    model.eval()
    return model


def _load_checkpoint(repo_id: str, filename: str, num_classes: int):
    """Download a RETFound fine-tune checkpoint and return a ready timm model.

    Used for the DR-grading model which uses a standard timm ViT-L head.
    Falls back to strict=False if the head key is absent (backbone still loads).
    """
    import timm
    import torch
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        cache_dir=_CACHE_DIR,  # nosec B108
        token=settings.HUGGINGFACE_API_KEY or None,
    )
    # weights_only=False needed: checkpoint contains argparse.Namespace which
    # PyTorch 2.6+ blocks by default. bswift/RETfound_eyepacs_DR is a trusted source.
    ckpt = torch.load(path, map_location="cpu", weights_only=False)  # nosec B614
    sd = ckpt.get("model", ckpt.get("model_state_dict", ckpt.get("state_dict", ckpt)))

    head = sd.get("head.weight")
    if head is None:
        logger.warning(
            "%s: no head.weight in checkpoint — loading backbone with strict=False", repo_id
        )
    elif head.shape[0] != num_classes:
        raise RuntimeError(f"{repo_id}: head has {head.shape[0]} classes, expected {num_classes}")

    # Detect the image size the checkpoint was trained on from pos_embed shape.
    # pos_embed: [1, N+1, 1024] where N = (img_size / patch_size)².
    # Standard RETFound (224px) → N=196 → 197 tokens.
    # bswift EYEPACS fine-tune (256px) → N=256 → 257 tokens.
    pe = sd.get("pos_embed")
    if pe is not None and pe.shape[1] == 257:
        img_size = 256  # 16×16 patches of size 16 → 256×256 input
    else:
        img_size = 224

    model = timm.create_model(
        "vit_large_patch16_224",
        pretrained=False,
        num_classes=num_classes,
        global_pool="avg",
        img_size=img_size,
    )
    model.load_state_dict(sd, strict=False)
    model.eval()
    return model, img_size


@lru_cache(maxsize=1)
def _odir_model():
    logger.info("Loading ODIR broad-disease model…")
    m = _load_odir_checkpoint()
    logger.info("ODIR model ready")
    return m


@lru_cache(maxsize=1)
def _dr_model():
    logger.info("Loading EYEPACS DR-grading model…")
    m, img_size = _load_checkpoint(_DR_REPO, _DR_FILE, len(_DR_LABELS))
    logger.info("DR-grading model ready (img_size=%d)", img_size)
    return m, img_size


def _preprocess(image_bytes: bytes, img_size: int = 224):
    """5-step fundus preprocessing pipeline.

    img_size controls the final crop: 224 for ODIR (standard RETFound),
    256 for models fine-tuned at that resolution (e.g. bswift EYEPACS DR).
    Steps 1–4 are image-size agnostic; only the final transform differs.
    """
    import cv2
    import numpy as np
    import torchvision.transforms as T
    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img_np = np.array(img)

    # Step 1: Circular FOV crop
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

    # Step 4: CLAHE on L channel (LAB space)
    img_lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    img_lab[:, :, 0] = clahe.apply(img_lab[:, :, 0])
    img_np = cv2.cvtColor(img_lab, cv2.COLOR_LAB2RGB)

    # Step 5: RETFound eval transform — resize to img_size+32 then centre-crop
    resize_to = max(img_size + 32, 256)
    transform = T.Compose(
        [
            T.Resize(resize_to, interpolation=T.InterpolationMode.BICUBIC),
            T.CenterCrop(img_size),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    return transform(Image.fromarray(img_np)).unsqueeze(0)  # [1, 3, img_size, img_size]


def _infer(model, tensor, labels: list[str]) -> dict[str, float]:
    import torch

    with torch.no_grad():
        probs = torch.softmax(model(tensor)[0], dim=0).tolist()
    return {label: round(prob, 4) for label, prob in zip(labels, probs)}


def _sync_analyze(image_bytes: bytes) -> dict | None:
    try:
        stage1 = _odir_model()
    except Exception as exc:
        logger.warning("ODIR model unavailable: %s", exc)
        return None

    tensor = _preprocess(image_bytes, img_size=224)
    odir_probs = _infer(stage1, tensor, _ODIR_LABELS)
    diabetes_prob = odir_probs.get("Diabetes", 0.0)

    # Stage 2: DR cascade
    dr_grading: dict | None = None
    if diabetes_prob >= _DR_CASCADE_THRESHOLD:
        try:
            dr_model, dr_img_size = _dr_model()
            dr_tensor = _preprocess(image_bytes, img_size=dr_img_size)
            dr_probs = _infer(dr_model, dr_tensor, _DR_LABELS)
            top_grade = max(dr_probs, key=dr_probs.get)
            dr_grading = {
                "top_grade": top_grade,
                "grade_confidence": dr_probs[top_grade],
                "all_grades": dr_probs,
            }
            logger.info(
                "DR cascade triggered (diabetes=%.0f%%) → %s (%.0f%%)",
                diabetes_prob * 100,
                top_grade,
                dr_probs[top_grade] * 100,
            )
        except Exception as exc:
            logger.warning("DR-grading model unavailable: %s", exc)

    # Top finding: when DR cascade ran and found actual disease, compare its
    # confidence against the highest non-Diabetes ODIR class and report whichever
    # is more confident. This prevents a Mild NPDR at 45% from burying a
    # Glaucoma finding at 63% just because the cascade fired.
    visible_odir = {k: v for k, v in odir_probs.items() if v >= _CONFIDENCE_THRESHOLD}
    if not visible_odir:
        visible_odir = {max(odir_probs, key=odir_probs.get): max(odir_probs.values())}

    if dr_grading and dr_grading["top_grade"] != "No DR":
        dr_top = dr_grading["top_grade"]
        dr_conf = dr_grading["grade_confidence"]
        # Best ODIR finding that isn't Diabetes (Diabetes is already captured by DR grading)
        odir_non_diabetes = {k: v for k, v in visible_odir.items() if k != "Diabetes"}
        odir_top = max(odir_non_diabetes, key=odir_non_diabetes.get) if odir_non_diabetes else None
        odir_top_conf = odir_non_diabetes[odir_top] if odir_top else 0.0
        if odir_top and odir_top_conf > dr_conf:
            top_finding = odir_top
            top_confidence = odir_top_conf
        else:
            top_finding = dr_top
            top_confidence = dr_conf
    else:
        top_finding = max(visible_odir, key=visible_odir.get)
        top_confidence = visible_odir[top_finding]

    result: dict = {
        "model": "RETFound-cascade (ODIR + EYEPACS-DR)",
        "top_finding": top_finding,
        "top_confidence": top_confidence,
        "all_findings": {k: v for k, v in odir_probs.items() if v >= _CONFIDENCE_THRESHOLD}
        or odir_probs,
    }
    if dr_grading:
        result["dr_grading"] = dr_grading

    return result


async def analyze(image_bytes: bytes) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_analyze, image_bytes)
