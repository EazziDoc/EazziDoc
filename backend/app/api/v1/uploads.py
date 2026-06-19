from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.upload import BatchUploadResponse, ImageUploadItem
from app.services.storage import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    StorageError,
    storage_service,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])

_ALLOWED_TYPES_STR = ", ".join(ALLOWED_CONTENT_TYPES)
MAX_IMAGES_PER_UPLOAD = 5


@router.post(
    "/images",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/hour")
async def upload_images(
    request: Request,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload 1–5 medical images to Cloudflare R2 for a single diagnosis session.

    All files are validated before any upload begins — the request fails fast
    if any file is invalid (wrong type, empty, or over 10 MB).

    Returns one entry per file with its object key and a 1-hour presigned URL.
    Pass the `image_keys` list when creating a diagnosis.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required",
        )
    if len(files) > MAX_IMAGES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {MAX_IMAGES_PER_UPLOAD} images per upload",
        )

    # ── validate all files before touching storage ────────────────────────────
    validated: list[tuple[bytes, str, str]] = []  # (data, content_type, key)

    for i, file in enumerate(files, start=1):
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"File {i} ({file.filename!r}): unsupported type "
                    f"'{file.content_type}'. Allowed: {_ALLOWED_TYPES_STR}"
                ),
            )

        data = await file.read()

        if len(data) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File {i} ({file.filename!r}) is empty",
            )
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {i} ({file.filename!r}) exceeds the 10 MB limit",
            )

        key = storage_service.make_image_key(str(current_user.id), file.content_type)
        validated.append((data, file.content_type, key))

    # ── upload all to R2 ──────────────────────────────────────────────────────
    results: list[ImageUploadItem] = []

    for data, content_type, key in validated:
        try:
            await storage_service.upload(data, key, content_type)
            url = await storage_service.presigned_url(key)
        except StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Image storage failed — please retry",
            ) from exc

        results.append(
            ImageUploadItem(
                image_key=key,
                presigned_url=url,
                size_bytes=len(data),
                content_type=content_type,
            )
        )

    return BatchUploadResponse(uploaded=results, total=len(results))
