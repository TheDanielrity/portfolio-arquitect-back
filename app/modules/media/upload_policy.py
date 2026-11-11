"""Central extension/MIME/size and bounded header inspection policy."""

from pathlib import PurePath

from app.core.config import Settings
from app.core.exceptions import InvalidOperation
from app.core.validation import database_text
from app.modules.media.storage_port import ObjectInfo
from app.modules.media.upload_schemas import UploadRequest

FORMATS = {
    ".jpg": ("image/jpeg", "IMAGE"),
    ".jpeg": ("image/jpeg", "IMAGE"),
    ".png": ("image/png", "IMAGE"),
    ".webp": ("image/webp", "IMAGE"),
    ".avif": ("image/avif", "IMAGE"),
    ".pdf": ("application/pdf", "PDF"),
    ".glb": ("model/gltf-binary", "MODEL_3D"),
    ".mp4": ("video/mp4", "VIDEO"),
    ".webm": ("video/webm", "VIDEO"),
}


def validate_request(body: UploadRequest, settings: Settings) -> tuple[str, str, int]:
    name = database_text(body.original_filename)
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise InvalidOperation("Filename must not contain a path")
    extension = PurePath(name).suffix.lower()
    entry = FORMATS.get(extension)
    if entry is None or body.mime_type != entry[0]:
        raise InvalidOperation("Unsupported file extension or MIME type")
    media_type = entry[1]
    limit = min(
        settings.media_max_file_size_bytes,
        {
            "IMAGE": settings.media_image_max_bytes,
            "PDF": settings.media_pdf_max_bytes,
            "MODEL_3D": settings.media_model_max_bytes,
            "VIDEO": settings.media_video_max_bytes,
        }[media_type],
    )
    if body.file_size > limit:
        raise InvalidOperation("Declared file size exceeds the configured limit")
    return extension, media_type, limit


def validate_object(
    info: ObjectInfo, prefix: bytes, body: UploadRequest, settings: Settings
) -> None:
    _, _, limit = validate_request(body, settings)
    if info.size != body.file_size or info.size > limit or info.mime_type != body.mime_type:
        raise InvalidOperation("Stored object size or MIME type does not match authorization")
    mime = body.mime_type
    valid = {
        "image/jpeg": prefix.startswith(b"\xff\xd8\xff"),
        "image/png": prefix.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP",
        "image/avif": prefix[4:8] == b"ftyp" and b"avif" in prefix[8:64],
        "application/pdf": prefix.startswith(b"%PDF-"),
        "model/gltf-binary": (
            prefix.startswith(b"glTF")
            and int.from_bytes(prefix[4:8], "little") == 2
            and int.from_bytes(prefix[8:12], "little") == info.size
        ),
        "video/mp4": prefix[4:8] == b"ftyp",
        "video/webm": prefix.startswith(b"\x1aE\xdf\xa3"),
    }[mime]
    if not valid:
        raise InvalidOperation("Object header is incompatible with the authorized format")
