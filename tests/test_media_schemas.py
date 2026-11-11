import pytest
from pydantic import ValidationError

from app.modules.media.schemas import MediaCreate, MediaUpdate
from app.modules.media.storage import StorageLocation


def payload(**overrides: object) -> dict[str, object]:
    return {
        "type": "IMAGE",
        "original_filename": "building.jpg",
        "storage_provider": "example",
        "storage_key": "portfolio/building.jpg",
        "url": "https://example.org/building.jpg",
        "mime_type": "image/jpeg",
        "file_size": 1024,
    } | overrides


@pytest.mark.parametrize("media_type", ["IMAGE", "VIDEO", "PDF", "MODEL_3D", "DOCUMENT"])
def test_all_media_types_allow_missing_dimensions(media_type: str) -> None:
    asset = MediaCreate.model_validate(payload(type=media_type))
    assert asset.type == media_type
    assert asset.width is None and asset.height is None


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "INVALID"},
        {"width": 0},
        {"height": -1},
        {"width": True},
        {"height": "100"},
        {"file_size": -1},
        {"file_size": 9223372036854775808},
        {"width": 2147483648},
        {"original_filename": "  "},
        {"storage_provider": ""},
        {"storage_key": "\t"},
        {"storage_key": "bad\x00key"},
        {"original_filename": "x" * 256},
        {"url": "javascript:alert(1)"},
        {"url": "https://user:private-password@example.org/image.jpg"},
        {"thumbnail_url": "https://private-token@example.org/image.jpg"},
        {"url": "https://example.org/" + "x" * 2048},
        {"thumbnail_url": "file:///image.png"},
        {"mime_type": "not-a-mime-type"},
        {"metadata": ["not-an-object"]},
        {"metadata": {"nested": ["\x00"]}},
        {"metadata": {"\x00": "value"}},
        {"metadata": {"surrogate": "\ud800"}},
        {"metadata": {"number": float("inf")}},
        {"metadata": {"huge": "x" * 65536}},
        {"unexpected": "value"},
    ],
)
def test_invalid_media_metadata_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MediaCreate.model_validate(payload(**changes))


def test_storage_keys_are_preserved_and_mime_type_normalized() -> None:
    location = StorageLocation(
        storage_provider="provider-two",
        storage_key=" Case Sensitive /Key ",
        url="https://example.org/a",
    )
    asset = MediaCreate.model_validate(
        payload(
            **location.model_dump(),
            mime_type="IMAGE/JPEG",
            metadata={"escaped": "\\u0000", "nested": [True, None, {"key": 1}]},
        )
    )
    assert asset.storage_key == " Case Sensitive /Key "
    assert asset.mime_type == "image/jpeg"
    assert asset.metadata is not None and asset.metadata["escaped"] == "\\u0000"


def test_patch_distinguishes_omitted_and_explicit_null_values() -> None:
    assert MediaUpdate().model_dump(exclude_unset=True) == {}
    assert MediaUpdate(title=None, metadata=None).model_dump(exclude_unset=True) == {
        "title": None,
        "metadata": None,
    }
    for field in ("storage_key", "storage_provider", "url", "type", "width", "file_size"):
        with pytest.raises(ValidationError):
            MediaUpdate.model_validate({field: None})
