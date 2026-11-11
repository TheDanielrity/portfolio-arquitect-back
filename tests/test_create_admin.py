import getpass
import sys
from unittest.mock import AsyncMock

import pytest

from app.modules.auth import create_admin


def test_provisioning_requires_interactive_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert create_admin.main() == 1
    assert "interactive terminal" in capsys.readouterr().err


@pytest.mark.parametrize("outcome", ["success", "mismatch", "short"])
def test_provisioning_prompts_hide_password_and_validate_before_database_access(
    outcome: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    inputs = iter(["admin@example.org", "Ada", "Lovelace"])
    password = "tiny" if outcome == "short" else "private-long-password"
    passwords = iter([password, "different-password" if outcome == "mismatch" else password])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(passwords))
    provision = AsyncMock(return_value=0)
    monkeypatch.setattr(create_admin, "provision", provision)
    assert create_admin.main() == (0 if outcome == "success" else 1)
    if outcome == "success":
        provision.assert_awaited_once()
        assert provision.call_args.args[0].password.get_secret_value() == password
    else:
        provision.assert_not_awaited()
    output = capsys.readouterr()
    assert password not in output.out + output.err
