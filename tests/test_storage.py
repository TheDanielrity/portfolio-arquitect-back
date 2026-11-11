from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.exceptions import InvalidOperation
from app.modules.media.dependencies import build_storage
from app.modules.media.storage_adapters import LocalStorageAdapter, R2StorageAdapter, check_key
from app.modules.media.storage_port import ObjectInfo, ObjectMissing, StorageError
from app.modules.media.upload_policy import FORMATS, validate_object, validate_request
from app.modules.media.upload_schemas import UploadRequest


def r2_settings() -> Settings:
    return Settings(
        storage_provider="r2",
        r2_account_id="a" * 32,
        r2_access_key_id=SecretStr("fake-access"),
        r2_secret_access_key=SecretStr("fake-secret"),
        r2_bucket_name="test-bucket",
    )


def test_provider_configuration_and_selection() -> None:
    assert isinstance(build_storage(Settings()), LocalStorageAdapter)
    assert isinstance(build_storage(r2_settings()), R2StorageAdapter)
    with pytest.raises(ValidationError):
        Settings(storage_provider="r2")
    with pytest.raises(ValidationError):
        Settings(media_base_url="https://secret:password@example.org")
    assert "fake-secret" not in repr(r2_settings())


@pytest.mark.parametrize(
    "filename,mime,size",
    [
        ("x.exe", "application/octet-stream", 5),
        ("x.gltf", "model/gltf+json", 5),
        ("x.jpg", "image/png", 5),
        ("../x.jpg", "image/jpeg", 5),
        ("x.jpg", "image/jpeg", 20971521),
        ("x.jpg\x00", "image/jpeg", 5),
    ],
)
def test_policy_rejects_invalid_declarations(filename: str, mime: str, size: int) -> None:
    with pytest.raises((InvalidOperation, ValueError)):
        validate_request(
            UploadRequest(original_filename=filename, mime_type=mime, file_size=size), Settings()
        )


@pytest.mark.parametrize("extension", FORMATS)
def test_allowed_formats_and_real_header_checks(extension: str) -> None:
    mime, _ = FORMATS[extension]
    headers = {
        "image/jpeg": b"\xff\xd8\xffx",
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/webp": b"RIFFxxxxWEBP",
        "image/avif": b"xxxxftypavif",
        "application/pdf": b"%PDF-1.7",
        "model/gltf-binary": b"glTF\x02\x00\x00\x00\x0c\x00\x00\x00",
        "video/mp4": b"xxxxftypisom",
        "video/webm": b"\x1aE\xdf\xa3",
    }
    data = headers[mime]
    body = UploadRequest(original_filename="x" + extension, mime_type=mime, file_size=len(data))
    validate_object(ObjectInfo(len(data), mime, "etag"), data, body, Settings())
    with pytest.raises(InvalidOperation):
        validate_object(ObjectInfo(len(data), mime, "etag"), b"invalid", body, Settings())
    with pytest.raises(InvalidOperation):
        validate_object(ObjectInfo(len(data) + 1, mime, "etag"), data, body, Settings())


@pytest.mark.parametrize(
    "key", ["../file", "objects/../x", "staging/fixed.jpg", "objects/" + "a" * 32 + ".jpg/other"]
)
def test_managed_key_validation(key: str) -> None:
    with pytest.raises(StorageError):
        check_key(key)


async def test_local_adapter_roundtrip(tmp_path: Path) -> None:
    adapter = LocalStorageAdapter(Settings(local_storage_path=tmp_path))
    source, target = f"staging/{uuid4().hex}.jpg", f"objects/{uuid4().hex}.jpg"
    with pytest.raises(ObjectMissing):
        await adapter.head(source)
    await adapter.put(source, b"\xff\xd8\xffdata", "image/jpeg")
    info = await adapter.head(source)
    assert info.size == 7 and info.mime_type == "image/jpeg"
    assert (
        await adapter.presign(source, "image/jpeg", datetime.now(UTC) + timedelta(seconds=60))
    ).headers == {"Content-Type": "image/jpeg"}
    assert await adapter.prefix(source, info.etag) == b"\xff\xd8\xffdata"
    await adapter.promote(source, target, info.etag)
    await adapter.put(source, b"different", "image/jpeg")
    assert (await adapter.head(target)).etag == info.etag
    with pytest.raises(StorageError):
        await adapter.promote(source, target, info.etag)
    await adapter.delete(target)
    await adapter.delete(target)
    with pytest.raises(ObjectMissing):
        await adapter.head(target)


async def test_r2_signed_contract_and_no_network() -> None:
    adapter = R2StorageAdapter(r2_settings())
    key = f"staging/{uuid4().hex}.jpg"
    with patch.object(
        adapter.client, "generate_presigned_url", return_value="https://signed.invalid"
    ) as signed:
        target = await adapter.presign(
            key, "image/jpeg", datetime.now(UTC) + timedelta(seconds=300)
        )
        assert target.headers == {"Content-Type": "image/jpeg"}
        assert signed.call_args.kwargs["Params"]["Key"] == key
        assert signed.call_args.kwargs["Params"]["ContentType"] == "image/jpeg"
        assert 1 <= signed.call_args.kwargs["ExpiresIn"] <= 300
        await adapter.access(key, 60)
        assert signed.call_args.args == ("get_object",)
        with pytest.raises(StorageError):
            await adapter.presign(key, "image/jpeg", datetime.now(UTC) - timedelta(seconds=1))


async def test_r2_head_prefix_copy_delete_and_errors() -> None:
    adapter = R2StorageAdapter(r2_settings())
    source, target = f"staging/{uuid4().hex}.jpg", f"objects/{uuid4().hex}.jpg"
    with Stubber(adapter.client) as stub:
        stub.add_response(
            "head_object",
            {"ContentLength": 7, "ContentType": "image/jpeg", "ETag": '"etag"'},
            {"Bucket": "test-bucket", "Key": source},
        )
        assert await adapter.head(source) == ObjectInfo(7, "image/jpeg", '"etag"')
        stream = StreamingBody(BytesIO(b"\xff\xd8\xffdata"), 7)
        stub.add_response(
            "get_object",
            {"Body": stream},
            {"Bucket": "test-bucket", "Key": source, "Range": "bytes=0-63", "IfMatch": '"etag"'},
        )
        assert await adapter.prefix(source, '"etag"') == b"\xff\xd8\xffdata"
        stub.add_response(
            "copy_object",
            {},
            {
                "Bucket": "test-bucket",
                "Key": target,
                "CopySource": {"Bucket": "test-bucket", "Key": source},
                "CopySourceIfMatch": '"etag"',
                "MetadataDirective": "COPY",
            },
        )
        await adapter.promote(source, target, '"etag"')
        stub.add_response("delete_object", {}, {"Bucket": "test-bucket", "Key": target})
        await adapter.delete(target)
        stub.add_client_error("head_object", "404", http_status_code=404)
        with pytest.raises(ObjectMissing):
            await adapter.head(source)
        stub.add_client_error("delete_object", "AccessDenied", "secret technical detail")
        with pytest.raises(StorageError, match="Storage unavailable") as error:
            await adapter.delete(source)
        assert "secret" not in str(error.value)
        stub.assert_no_pending_responses()
