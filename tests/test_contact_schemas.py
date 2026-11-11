import pytest
from pydantic import ValidationError

from app.modules.contact.schemas import ContactCreate, ContactStatusUpdate


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"name": "x" * 151},
        {"email": "invalid"},
        {"email": "a@@example.org"},
        {"email": "a..b@example.org"},
        {"email": "a@-example.org"},
        {"email": "a\n@example.org"},
        {"phone": "x" * 51},
        {"phone": " "},
        {"subject": "x" * 201},
        {"message": " \n\t"},
        {"message": "x" * 10001},
        {"message": "bad\x00text"},
        {"message": "bad\ud800"},
        {"status": "READ"},
        {"ip_address": "127.0.0.1"},
        {"read_at": "2026-09-30T00:00:00Z"},
        {"user_agent": "fake"},
    ],
)
def test_invalid_contact_input(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ContactCreate.model_validate(
            {"name": "Ada", "email": "ada@example.org", "message": "Hello"} | changes
        )


def test_contact_normalization_and_optional_fields() -> None:
    body = ContactCreate(
        name=" Ada ", email="ada@EXAMPLE.ORG", message=" Hello\nworld ", phone=None, subject=None
    )
    assert body.name == "Ada" and body.email == "ada@example.org"
    assert body.message == "Hello\nworld" and body.phone is None and body.subject is None


@pytest.mark.parametrize("body", [{"status": "NEW"}, {"status": "INVALID"}, {}, {"status": None}])
def test_invalid_status_updates(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ContactStatusUpdate.model_validate(body)
