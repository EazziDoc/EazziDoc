from pydantic import BaseModel


class ImageUploadItem(BaseModel):
    image_key: str
    presigned_url: str
    size_bytes: int
    content_type: str


class BatchUploadResponse(BaseModel):
    uploaded: list[ImageUploadItem]
    total: int
