from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        "APP_NAME",
        "APP_ENV",
        "DEBUG",
        "CORS_ORIGINS",
        "JWT_ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "MAX_REQUEST_BODY_BYTES",
        "AUTH_REQUESTS_PER_MINUTE",
        "CONTACT_REQUESTS_PER_MINUTE",
        "STORAGE_PROVIDER",
        "MEDIA_BASE_URL",
        "LOCAL_STORAGE_PATH",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
        "R2_PUBLIC_BASE_URL",
        "R2_PRESIGNED_URL_EXPIRE_SECONDS",
        "MEDIA_CLEANUP_GRACE_SECONDS",
        "MEDIA_MAX_FILE_SIZE_BYTES",
        "MEDIA_IMAGE_MAX_BYTES",
        "MEDIA_PDF_MAX_BYTES",
        "MEDIA_MODEL_MAX_BYTES",
        "MEDIA_VIDEO_MAX_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-key-for-isolated-tests-0123456789")
