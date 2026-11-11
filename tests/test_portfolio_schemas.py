from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.portfolio.schemas import (
    Assignment,
    AttributeUpdate,
    CategoryUpdate,
    MediaLinkUpdate,
    ProjectCreate,
    ProjectUpdate,
    Reorder,
    TagUpdate,
)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"title": "x" * 201},
        {"title": "bad\x00title"},
        {"slug": "two words"},
        {"slug": "bad--slug"},
        {"slug": "-bad"},
        {"slug": "x" * 221},
        {"year": 1799},
        {"year": 2201},
        {"year": True},
        {"area_m2": 0},
        {"area_m2": "1.001"},
        {"area_m2": "10000000000"},
        {"area_m2": "NaN"},
        {"status": "unknown"},
        {"visibility": "unknown"},
        {"sort_order": -1},
        {"sort_order": True},
        {"sort_order": 2147483648},
        {"deleted_at": None},
        {"published_at": None},
    ],
)
def test_project_rejects_invalid_input(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"title": "House", "slug": "house"} | changes)


def test_normalization_and_patch_semantics() -> None:
    body = ProjectCreate(title=" House ", slug=" HOUSE-ONE ")
    assert body.title == "House" and body.slug == "house-one"
    assert ProjectUpdate().model_dump(exclude_unset=True) == {}
    assert ProjectUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}


@pytest.mark.parametrize(
    "model,field",
    [
        (ProjectUpdate, "title"),
        (ProjectUpdate, "status"),
        (ProjectUpdate, "visibility"),
        (ProjectUpdate, "slug"),
        (ProjectUpdate, "sort_order"),
        (ProjectUpdate, "is_featured"),
        (CategoryUpdate, "is_active"),
        (TagUpdate, "name"),
        (AttributeUpdate, "value"),
        (MediaLinkUpdate, "role"),
    ],
)
def test_required_fields_cannot_be_cleared(
    model: type[ProjectUpdate | CategoryUpdate | TagUpdate | AttributeUpdate | MediaLinkUpdate],
    field: str,
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({field: None})


def test_assignments_and_reorder_validate_duplicate_ids_but_allow_tied_orders() -> None:
    first, second = uuid4(), uuid4()
    with pytest.raises(ValidationError):
        Assignment(ids=[first, first])
    with pytest.raises(ValidationError):
        Reorder.model_validate({"items": [{"id": first, "sort_order": 0}] * 2})
    assert Assignment(ids=[]).ids == []
    assert (
        len(
            Reorder.model_validate(
                {
                    "items": [
                        {"id": first, "sort_order": 0},
                        {"id": second, "sort_order": 0},
                    ]
                }
            ).items
        )
        == 2
    )
