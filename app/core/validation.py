"""Validation shared by database inputs and public delivery URLs."""

from typing import Annotated

from pydantic import AfterValidator, AnyHttpUrl, Field


def database_text(value: str) -> str:
    """Reject text PostgreSQL cannot store, preserving valid input exactly."""
    if "\x00" in value:
        raise ValueError("Text must not contain NUL characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Text must contain valid Unicode") from exc
    return value


def public_url(value: AnyHttpUrl) -> AnyHttpUrl:
    if value.username is not None or value.password is not None:
        raise ValueError("URLs must not contain credentials")
    return value


WebUrl = Annotated[AnyHttpUrl, Field(max_length=2048), AfterValidator(public_url)]
