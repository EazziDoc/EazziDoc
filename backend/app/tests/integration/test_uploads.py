from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.services.storage import storage_service

_USER = {
    "email": "uploader@upload-tests.dev",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Test",
    "last_name": "Upload",
}

_FAKE_URL = "https://r2.example.com/presigned?sig=test"


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/register", json=_USER)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _USER["email"], "password": _USER["password"]},
    )
    return resp.json()["access_token"]


def _r2_patches():
    return (
        patch.object(storage_service, "upload", new_callable=AsyncMock),
        patch.object(storage_service, "presigned_url", new_callable=AsyncMock),
    )


# ── success: single file ──────────────────────────────────────────────────────


async def test_upload_single_jpeg(client: AsyncClient):
    token = await _token(client)

    with (
        patch.object(storage_service, "upload", new_callable=AsyncMock),
        patch.object(storage_service, "presigned_url", new_callable=AsyncMock) as mp,
    ):
        mp.return_value = _FAKE_URL

        resp = await client.post(
            "/api/v1/uploads/images",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("left_eye.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg"))],
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] == 1
    item = data["uploaded"][0]
    assert item["image_key"].startswith("images/")
    assert item["image_key"].endswith(".jpg")
    assert item["presigned_url"] == _FAKE_URL
    assert item["size_bytes"] > 0
    assert item["content_type"] == "image/jpeg"


# ── success: multiple files ───────────────────────────────────────────────────


async def test_upload_two_images(client: AsyncClient):
    token = await _token(client)

    with (
        patch.object(storage_service, "upload", new_callable=AsyncMock),
        patch.object(storage_service, "presigned_url", new_callable=AsyncMock) as mp,
    ):
        mp.return_value = _FAKE_URL

        resp = await client.post(
            "/api/v1/uploads/images",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", ("left.jpg", b"\xff\xd8\xff" + b"a" * 50, "image/jpeg")),
                ("files", ("right.png", b"\x89PNG" + b"b" * 50, "image/png")),
            ],
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] == 2
    assert len(data["uploaded"]) == 2
    # each file gets its own unique key
    keys = {item["image_key"] for item in data["uploaded"]}
    assert len(keys) == 2


async def test_upload_five_images_max_allowed(client: AsyncClient):
    token = await _token(client)

    with (
        patch.object(storage_service, "upload", new_callable=AsyncMock),
        patch.object(storage_service, "presigned_url", new_callable=AsyncMock) as mp,
    ):
        mp.return_value = _FAKE_URL

        files = [
            ("files", (f"img{i}.jpg", b"\xff\xd8\xff" + b"x" * 20, "image/jpeg")) for i in range(5)
        ]
        resp = await client.post(
            "/api/v1/uploads/images",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )

    assert resp.status_code == 201
    assert resp.json()["total"] == 5


# ── auth guard ────────────────────────────────────────────────────────────────


async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/uploads/images",
        files=[("files", ("scan.jpg", b"data", "image/jpeg"))],
    )
    assert resp.status_code == 403


# ── validation ────────────────────────────────────────────────────────────────


async def test_upload_rejects_more_than_five(client: AsyncClient):
    token = await _token(client)
    files = [
        ("files", (f"img{i}.jpg", b"\xff\xd8\xff" + b"x" * 10, "image/jpeg")) for i in range(6)
    ]
    resp = await client.post(
        "/api/v1/uploads/images",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert resp.status_code == 422


async def test_upload_rejects_unsupported_type(client: AsyncClient):
    token = await _token(client)
    resp = await client.post(
        "/api/v1/uploads/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("report.pdf", b"%PDF-1.4", "application/pdf"))],
    )
    assert resp.status_code == 415


async def test_upload_rejects_empty_file(client: AsyncClient):
    token = await _token(client)
    resp = await client.post(
        "/api/v1/uploads/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("empty.jpg", b"", "image/jpeg"))],
    )
    assert resp.status_code == 422


async def test_upload_rejects_oversized_file(client: AsyncClient):
    token = await _token(client)
    big = b"x" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte
    resp = await client.post(
        "/api/v1/uploads/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("huge.jpg", big, "image/jpeg"))],
    )
    assert resp.status_code == 413


async def test_upload_fails_fast_on_invalid_second_file(client: AsyncClient):
    """Validation is done before any upload: one bad file fails the whole request."""
    token = await _token(client)
    resp = await client.post(
        "/api/v1/uploads/images",
        headers={"Authorization": f"Bearer {token}"},
        files=[
            ("files", ("ok.jpg", b"\xff\xd8\xff" + b"x" * 20, "image/jpeg")),
            ("files", ("bad.pdf", b"%PDF", "application/pdf")),
        ],
    )
    assert resp.status_code == 415  # rejected before upload


# ── storage failure ───────────────────────────────────────────────────────────


async def test_upload_returns_502_on_r2_failure(client: AsyncClient):
    from botocore.exceptions import ClientError

    token = await _token(client)

    with patch.object(storage_service, "upload", new_callable=AsyncMock) as mu:
        mu.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}}, "PutObject"
        )
        resp = await client.post(
            "/api/v1/uploads/images",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("scan.jpg", b"\xff\xd8\xff" + b"x" * 10, "image/jpeg"))],
        )

    assert resp.status_code == 502
