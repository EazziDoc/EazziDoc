import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tiff",
    "application/dicom": "dcm",
}
ALLOWED_CERT_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="r2")


def _build_client():
    return boto3.client(
        "s3",
        endpoint_url=(f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"),
        aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


class StorageService:
    def __init__(self) -> None:
        self._client = None

    @property
    def _r2(self):
        if self._client is None:
            self._client = _build_client()
        return self._client

    # ── sync helpers (run in thread pool) ────────────────────────────────────

    def _sync_upload(self, data: bytes, key: str, content_type: str) -> str:
        self._r2.put_object(
            Bucket=settings.CLOUDFLARE_R2_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def _sync_presign(self, key: str, expires_in: int) -> str:
        return self._r2.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.CLOUDFLARE_R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )

    def _sync_delete(self, key: str) -> None:
        self._r2.delete_object(
            Bucket=settings.CLOUDFLARE_R2_BUCKET_NAME,
            Key=key,
        )

    # ── async public API ──────────────────────────────────────────────────────

    async def upload(self, data: bytes, key: str, content_type: str) -> str:
        """Upload bytes to R2; returns the object key."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _executor, partial(self._sync_upload, data, key, content_type)
        )

    async def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a time-limited presigned GET URL for the given key."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, partial(self._sync_presign, key, expires_in))

    async def delete(self, key: str) -> None:
        """Delete an object from R2."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_executor, partial(self._sync_delete, key))

    def make_image_key(self, user_id: str, content_type: str) -> str:
        """Generate a deterministic, collision-free object key for an image."""
        ext = ALLOWED_CONTENT_TYPES[content_type]
        return f"images/{user_id}/{uuid.uuid4()}.{ext}"

    def make_cert_key(self, user_id: str, content_type: str) -> str:
        """Generate an object key for a doctor certification document."""
        ext = ALLOWED_CERT_TYPES[content_type]
        return f"certifications/{user_id}/{uuid.uuid4()}.{ext}"


StorageError = (BotoCoreError, ClientError)

storage_service = StorageService()
