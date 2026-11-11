from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import OperationalError

from app.core.check_database import check_database
from app.core.database import Database


@pytest.mark.parametrize("success", [True, False])
async def test_connection_check_result_and_cleanup(
    success: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verify = AsyncMock()
    if not success:
        verify.side_effect = OperationalError("SELECT 1", None, Exception("private-password"))
    dispose = AsyncMock()
    monkeypatch.setattr(Database, "verify_connection", verify)
    monkeypatch.setattr(Database, "dispose", dispose)
    assert await check_database() == (0 if success else 1)
    verify.assert_awaited_once()
    dispose.assert_awaited_once()
    output = capsys.readouterr().err
    assert "private-password" not in output
    assert ("verified" if success else "failed") in output


async def test_connection_check_missing_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    assert await check_database() == 1
    assert "Invalid database configuration" in capsys.readouterr().err
