from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.portfolio.section_schemas import SectionCreate, SectionMediaUpdate, SectionUpdate


@pytest.mark.parametrize(
    "changes",
    [
        {"section_type": "INVALID"},
        {"sort_order": -1},
        {"sort_order": True},
        {"title": "x" * 201},
        {"content": "x" * 50001},
        {"content": "bad\x00text"},
        {"media": [{"media_id": str(uuid4()), "caption": "x" * 256}]},
        {"media": [{"media_id": str(uuid4()), "sort_order": -1}]},
        {"project_id": str(uuid4())},
    ],
)
def test_invalid_section_inputs(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SectionCreate.model_validate({"section_type": "TEXT", "content": "Content"} | changes)


@pytest.mark.parametrize("field", ["section_type", "sort_order", "is_visible", "media"])
def test_required_section_fields_cannot_be_cleared(field: str) -> None:
    with pytest.raises(ValidationError):
        SectionUpdate.model_validate({field: None})


def test_section_media_limits_duplicates_and_patch_semantics() -> None:
    item = {"media_id": str(uuid4())}
    for model in (SectionCreate, SectionUpdate):
        with pytest.raises(ValidationError):
            model.model_validate({"section_type": "GALLERY", "media": [item, item]})
        with pytest.raises(ValidationError):
            model.model_validate(
                {
                    "section_type": "GALLERY",
                    "media": [{"media_id": str(uuid4())} for _ in range(101)],
                }
            )
    assert SectionUpdate().model_dump(exclude_unset=True) == {}
    assert SectionUpdate(content=None).model_dump(exclude_unset=True) == {"content": None}
    assert SectionMediaUpdate(caption=None).model_dump(exclude_unset=True) == {"caption": None}
    with pytest.raises(ValidationError):
        SectionMediaUpdate(sort_order=None)
