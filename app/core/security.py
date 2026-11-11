"""Password hashing, signed access tokens and opaque refresh-token secrets."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import Settings
from app.core.exceptions import AuthenticationError


@dataclass(frozen=True)
class AccessIdentity:
    user_id: UUID
    session_id: UUID


class Security:
    """One application's security configuration, with no shared session state."""

    def __init__(self, settings: Settings) -> None:
        self._key = settings.jwt_secret_key.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._passwords = PasswordHash.recommended()
        self._dummy_hash = self._passwords.hash(secrets.token_urlsafe(32))

    def hash_password(self, password: str) -> str:
        return self._passwords.hash(password)

    def verify_password(self, password: str, stored_hash: str | None) -> tuple[bool, str | None]:
        """Perform Argon2 verification even when the email is unknown."""
        try:
            valid, updated = self._passwords.verify_and_update(
                password, stored_hash if stored_hash is not None else self._dummy_hash
            )
        except UnknownHashError:
            self._passwords.verify(password, self._dummy_hash)
            return False, None
        return (valid, updated) if stored_hash is not None else (False, None)

    def create_access_token(
        self, user_id: UUID, session_id: UUID, now: datetime, expires_at: datetime
    ) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "jti": str(uuid4()),
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
                "type": "access",
                "iss": "architecture-portfolio",
                "aud": "architecture-portfolio-admin",
            },
            self._key,
            algorithm=self._algorithm,
        )

    def decode_access_token(self, token: str) -> AccessIdentity:
        if len(token) > 4096:
            raise AuthenticationError
        try:
            claims = jwt.decode(
                token,
                self._key,
                algorithms=[self._algorithm],
                issuer="architecture-portfolio",
                audience="architecture-portfolio-admin",
                options={
                    "require": ["sub", "sid", "jti", "iat", "nbf", "exp", "type", "iss", "aud"]
                },
            )
            if claims["type"] != "access":
                raise AuthenticationError
            if any(type(claims[key]) is not int for key in ("iat", "nbf", "exp")):
                raise AuthenticationError
            if claims["exp"] <= claims["iat"] or claims["exp"] <= claims["nbf"]:
                raise AuthenticationError
            UUID(claims["jti"])
            return AccessIdentity(UUID(claims["sub"]), UUID(claims["sid"]))
        except (jwt.PyJWTError, ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise AuthenticationError from exc


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
