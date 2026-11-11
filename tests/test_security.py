from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import Security, hash_refresh_token, new_refresh_token


@pytest.fixture
def security() -> Security:
    return Security(Settings())


def test_argon2_hashes_and_verifies_without_normalizing_password(security: Security) -> None:
    password = " correct horse battery staple "
    hashed = security.hash_password(password)
    assert hashed.startswith("$argon2id$")
    assert password not in hashed
    assert security.hash_password(password) != hashed
    assert security.verify_password(password, hashed) == (True, None)
    assert security.verify_password(password.strip(), hashed) == (False, None)
    assert security.verify_password(password, None) == (False, None)
    assert security.verify_password(password, "not-a-hash") == (False, None)


def test_older_argon2_hash_is_upgraded(security: Security) -> None:
    previous = PasswordHash((Argon2Hasher(time_cost=1),)).hash("long-test-password")
    valid, replacement = security.verify_password("long-test-password", previous)
    assert valid and replacement is not None and replacement != previous
    assert security.verify_password("long-test-password", replacement) == (True, None)


def test_refresh_secrets_are_random_and_only_hashes_are_persistable() -> None:
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second and len(first) == len(second) == 64
    assert len(hash_refresh_token(first)) == 64
    assert hash_refresh_token(first) != first
    assert hash_refresh_token(first) != hash_refresh_token(second)


def test_access_token_roundtrip(security: Security) -> None:
    user_id, session_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    token = security.create_access_token(user_id, session_id, now, now + timedelta(minutes=15))
    identity = security.decode_access_token(token)
    assert identity.user_id == user_id and identity.session_id == session_id


@pytest.mark.parametrize(
    "change",
    [
        "expired",
        "future",
        "wrong_issuer",
        "wrong_audience",
        "wrong_type",
        "missing_exp",
        "missing_sid",
        "invalid_sub",
        "invalid_sid",
        "invalid_jti",
        "string_exp",
        "bool_iat",
        "infinite_exp",
        "infinite_iat",
        "nan_exp",
        "wrong_key",
        "wrong_algorithm",
        "unsigned",
    ],
)
def test_invalid_access_tokens_are_rejected(security: Security, change: str) -> None:
    now = int(datetime.now(UTC).timestamp())
    claims: dict[str, object] = {
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "jti": str(uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "type": "access",
        "iss": "architecture-portfolio",
        "aud": "architecture-portfolio-admin",
    }
    key = Settings().jwt_secret_key.get_secret_value()
    algorithm = "HS256"
    changes: dict[str, dict[str, object]] = {
        "expired": {"iat": now - 1000, "nbf": now - 1000, "exp": now - 1},
        "future": {"iat": now + 60, "nbf": now + 60},
        "wrong_issuer": {"iss": "other"},
        "wrong_audience": {"aud": "other"},
        "wrong_type": {"type": "refresh"},
        "invalid_sub": {"sub": "invalid"},
        "invalid_sid": {"sid": []},
        "invalid_jti": {"jti": "invalid"},
        "string_exp": {"exp": str(now + 900)},
        "bool_iat": {"iat": True},
        "infinite_exp": {"exp": float("inf")},
        "infinite_iat": {"iat": float("inf")},
        "nan_exp": {"exp": float("nan")},
    }
    claims.update(changes.get(change, {}))
    if change.startswith("missing_"):
        claims.pop(change.removeprefix("missing_"))
    if change == "wrong_key":
        key = "unrelated-secret-key-with-at-least-64-bytes-for-hmac-testing-0123456789"
    if change == "wrong_algorithm":
        algorithm = "HS512"
        key = key.ljust(64, "x")
    if change == "unsigned":
        algorithm, key = "none", ""
    token = jwt.encode(claims, key, algorithm=algorithm)
    with pytest.raises(AuthenticationError):
        security.decode_access_token(token)


@pytest.mark.parametrize("token", ["", "not.a.jwt", "x" * 4097])
def test_malformed_access_tokens_are_rejected(security: Security, token: str) -> None:
    with pytest.raises(AuthenticationError):
        security.decode_access_token(token)
