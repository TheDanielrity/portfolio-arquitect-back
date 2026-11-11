"""Shared validation for administrative search and ordering."""

from typing import Annotated, Literal

from pydantic import AfterValidator, StringConstraints


def valid_search(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Search must not contain NUL")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Search must contain valid Unicode") from exc
    return value


Search = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(valid_search),
]
Direction = Literal["asc", "desc"]
