import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from app.core.database import Database
from app.core.security import Security
from app.models import (
    Category,
    MediaAsset,
    Profile,
    Project,
    ProjectAttribute,
    ProjectCategory,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
    ProjectTag,
    Service,
    SiteSetting,
    SocialLink,
    Tag,
)
from tests.migration_support import migrate, temporary_databases
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize
from tests.test_portfolio_integration import asset, project

BASE = "/api/v1/public"
pytestmark = pytest.mark.integration
FORBIDDEN = {
    "id",
    "project_id",
    "media_id",
    "section_id",
    "profile_id",
    "storage_key",
    "storage_provider",
    "original_filename",
    "metadata",
    "asset_metadata",
    "created_at",
    "updated_at",
    "deleted_at",
    "status",
    "visibility",
    "is_active",
    "is_visible",
    "password_hash",
    "token_hash",
    "sort_order",
}


def assert_public(value: object) -> None:
    if isinstance(value, dict):
        assert not FORBIDDEN.intersection(value)
        for child in value.values():
            assert_public(child)
    elif isinstance(value, list):
        for child in value:
            assert_public(child)


@pytest.fixture
def public_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated public API tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


@contextmanager
def select_count(database: Database) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(database.engine.sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(database.engine.sync_engine, "before_cursor_execute", record)


def media(kind: str = "IMAGE", label: str = "asset") -> MediaAsset:
    return MediaAsset(
        type=kind,
        storage_provider="private-provider",
        storage_key=uuid4().hex,
        original_filename="internal-name",
        url=f"https://assets.example.org/{label}",
        mime_type="image/jpeg" if kind == "IMAGE" else "application/pdf",
        file_size=10,
        asset_metadata={"internal": "secret-marker"},
        alt_text="Facade",
    )


def test_complete_visibility_matrix_listing_detail_and_featured(public_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        expected = []
        now = datetime.now(UTC)
        async with database.session() as session, session.begin():
            for status in ("PUBLISHED", "DRAFT", "ARCHIVED"):
                for visibility in ("PUBLIC", "UNLISTED", "PRIVATE"):
                    for deleted in (False, True):
                        slug = f"{status}-{visibility}-{deleted}".lower()
                        row = Project(
                            title=slug,
                            slug=slug,
                            status=status,
                            visibility=visibility,
                            is_featured=(status == "PUBLISHED" and visibility == "PUBLIC"),
                            created_at=now,
                            published_at=now,
                            deleted_at=now if deleted else None,
                        )
                        session.add(row)
                        expected.append(
                            (
                                slug,
                                status == "PUBLISHED" and visibility != "PRIVATE" and not deleted,
                            )
                        )
        for endpoint in ("projects", "featured-projects"):
            response = await client.get(f"{BASE}/{endpoint}")
            assert response.status_code == 200, response.text
            assert response.json()["total"] == 1
            assert response.json()["items"][0]["slug"] == "published-public-false"
            assert response.headers["Cache-Control"] == "no-store"
            assert_public(response.json())
        for slug, allowed in expected:
            response = await client.get(f"{BASE}/projects/{slug}")
            assert response.status_code == (200 if allowed else 404), (slug, response.text)
            if allowed:
                assert_public(response.json())
            else:
                assert response.json() == {"detail": "Project not found"}
        assert (await client.get(f"{BASE}/projects/missing")).status_code == 404

    exercise(public_database, check)


def test_filters_taxonomy_discovery_ordering_and_query_count(public_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        async with database.session() as session, session.begin():
            category = Category(name="Housing", slug="housing")
            hidden_category = Category(name="Hidden", slug="hidden", is_active=False)
            secret_category = Category(name="Secret", slug="secret")
            tag = Tag(name="Concrete", slug="concrete")
            secret_tag = Tag(name="Secret", slug="secret")
            session.add_all([category, hidden_category, secret_category, tag, secret_tag])
            await session.flush()
            for index in range(3):
                row = Project(
                    title=f"House {index}",
                    slug=f"house-{index}",
                    status="PUBLISHED",
                    sort_order=2 - index,
                    is_featured=index == 2,
                )
                cover = media(label=f"cover-{index}")
                session.add_all([row, cover])
                await session.flush()
                session.add_all(
                    [
                        ProjectCategory(project_id=row.id, category_id=category.id),
                        ProjectCategory(project_id=row.id, category_id=hidden_category.id),
                        ProjectMedia(project_id=row.id, media_id=cover.id, role="COVER"),
                        ProjectTag(project_id=row.id, tag_id=tag.id),
                    ]
                )
            for visibility in ("PRIVATE", "UNLISTED"):
                row = Project(
                    title=visibility,
                    slug=visibility.lower(),
                    status="PUBLISHED",
                    visibility=visibility,
                )
                session.add(row)
                await session.flush()
                session.add_all(
                    [
                        ProjectCategory(project_id=row.id, category_id=secret_category.id),
                        ProjectTag(project_id=row.id, tag_id=secret_tag.id),
                    ]
                )
        for limit in (1, 3):
            with select_count(database) as statements:
                response = await client.get(f"{BASE}/projects", params={"limit": limit})
            assert response.status_code == 200, response.text
            assert len(statements) == 4
            assert len(response.json()["items"]) == limit and response.json()["total"] == 3
            assert response.json()["items"][0]["cover"]["url"].endswith("cover-2")
            assert [item["slug"] for item in response.json()["items"][0]["categories"]] == [
                "housing"
            ]
            assert_public(response.json())
        page = (await client.get(f"{BASE}/projects", params={"limit": 1, "offset": 1})).json()
        assert page["items"][0]["slug"] == "house-1"
        assert (await client.get(f"{BASE}/projects", params={"offset": 99})).json()["items"] == []
        for query, total in (
            ({"category": "HOUSING", "tag": "concrete"}, 3),
            ({"category": "hidden"}, 0),
            ({"category": "secret"}, 0),
            ({"tag": "secret"}, 0),
            ({"category": "missing"}, 0),
        ):
            assert (await client.get(f"{BASE}/projects", params=query)).json()["total"] == total
        assert (await client.get(f"{BASE}/featured-projects")).json()["total"] == 1
        for endpoint, slug in (("categories", "housing"), ("tags", "concrete")):
            data = (await client.get(f"{BASE}/{endpoint}")).json()
            assert data["total"] == 1 and data["items"][0]["slug"] == slug
            assert_public(data)
            assert (await client.get(f"{BASE}/{endpoint}?offset=1")).json()["items"] == []

    exercise(public_database, check)


def test_publication_changes_slug_reuse_and_featured_slug(public_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        row = await project(client, slug="featured", is_featured=True)
        path = f"/api/v1/admin/projects/{row['id']}"
        cover = await asset(client)
        assert (await client.put(path + "/cover", json={"media_id": cover})).status_code == 200
        assert (await client.get(f"{BASE}/projects/featured")).status_code == 404
        assert (await client.patch(path, json={"status": "PUBLISHED"})).status_code == 200
        assert (await client.get(f"{BASE}/projects/featured")).status_code == 200
        for visibility, direct, total in (
            ("PRIVATE", 404, 0),
            ("UNLISTED", 200, 0),
            ("PUBLIC", 200, 1),
        ):
            assert (await client.patch(path, json={"visibility": visibility})).status_code == 200
            assert (await client.get(f"{BASE}/projects/featured")).status_code == direct
            assert (await client.get(f"{BASE}/featured-projects")).json()["total"] == total
        assert (await client.patch(path, json={"status": "ARCHIVED"})).status_code == 200
        assert (await client.get(f"{BASE}/projects/featured")).status_code == 404
        assert (await client.patch(path, json={"status": "PUBLISHED"})).status_code == 200
        assert (await client.delete(path)).status_code == 204
        replacement = await project(client, slug="featured", title="Replacement")
        # An old published row with this slug must never bypass the replacement's draft state.
        assert (await client.get(f"{BASE}/projects/featured")).status_code == 404
        replacement_path = f"/api/v1/admin/projects/{replacement['id']}"
        assert (
            await client.put(replacement_path + "/cover", json={"media_id": cover})
        ).status_code == 200
        assert (
            await client.patch(replacement_path, json={"status": "PUBLISHED"})
        ).status_code == 200
        assert (await client.get(f"{BASE}/projects/featured")).json()["title"] == "Replacement"

    exercise(public_database, check)


def test_detail_composes_all_section_types_and_safe_media(public_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        kinds = ("TEXT", "IMAGE", "GALLERY", "VIDEO", "MODEL_3D", "QUOTE", "SPLIT")
        async with database.session() as session, session.begin():
            row = Project(
                title="House",
                slug="house",
                status="PUBLISHED",
                description="Narrative",
                area_m2=Decimal("120.50"),
                client_name="Client",
                seo_title="House design",
            )
            cover, document = media(label="cover"), media("PDF", "document")
            session.add_all([row, cover, document])
            await session.flush()
            session.add_all(
                [
                    ProjectMedia(project_id=row.id, media_id=cover.id, role="COVER"),
                    ProjectMedia(project_id=row.id, media_id=document.id, role="DOCUMENT"),
                    ProjectAttribute(project_id=row.id, label="Second", value="B", sort_order=2),
                    ProjectAttribute(project_id=row.id, label="First", value="A", sort_order=1),
                    ProjectSection(
                        project_id=row.id,
                        section_type="TEXT",
                        content="hidden-marker",
                        is_visible=False,
                    ),
                ]
            )
            for index, kind in enumerate(kinds):
                section = ProjectSection(
                    project_id=row.id,
                    section_type=kind,
                    title=kind,
                    content="Section text",
                    sort_order=index,
                )
                session.add(section)
                await session.flush()
                if kind not in {"TEXT", "QUOTE"}:
                    asset = media(kind if kind in {"VIDEO", "MODEL_3D"} else "IMAGE", kind.lower())
                    session.add(asset)
                    await session.flush()
                    session.add(
                        ProjectSectionMedia(
                            section_id=section.id,
                            media_id=asset.id,
                            caption="Caption",
                            sort_order=1,
                        )
                    )
                    if kind == "GALLERY":
                        session.add(
                            ProjectSectionMedia(
                                section_id=section.id,
                                media_id=cover.id,
                                caption="First",
                                sort_order=0,
                            )
                        )
        with select_count(database) as statements:
            response = await client.get(f"{BASE}/projects/house")
        assert response.status_code == 200, response.text
        assert len(statements) == 7
        body = response.json()
        assert_public(body)
        assert "secret-marker" not in response.text and "hidden-marker" not in response.text
        assert body["area_m2"] == "120.50" and body["description"] == "Narrative"
        assert body["seo_title"] == "House design"
        assert [item["label"] for item in body["attributes"]] == ["First", "Second"]
        assert [item["section_type"] for item in body["sections"]] == list(kinds)
        gallery = body["sections"][2]["media"]
        assert [item["caption"] for item in gallery] == ["First", "Caption"]
        pdf = next(item["asset"] for item in body["media"] if item["role"] == "DOCUMENT")
        assert pdf["type"] == "PDF" and pdf["width"] is None and pdf["height"] is None

    exercise(public_database, check)


def test_legacy_media_credentials_never_enter_public_responses(public_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        async with database.session() as session, session.begin():
            row = Project(title="Legacy", slug="legacy", status="PUBLISHED")
            cover = media(label="legacy")
            cover.url = "https://user:private-password@example.org/image.jpg"
            session.add_all([row, cover])
            await session.flush()
            session.add(ProjectMedia(project_id=row.id, media_id=cover.id, role="COVER"))
        for path in (f"{BASE}/projects", f"{BASE}/projects/legacy"):
            response = await client.get(path)
            assert response.status_code == 500
            assert response.json() == {"detail": "Internal server error"}
            assert "private-password" not in response.text
        async with database.session() as session, session.begin():
            stored = await session.get(MediaAsset, cover.id)
            assert stored is not None
            stored.url = "https://example.org/image.jpg"
        assert (await client.get(f"{BASE}/projects/legacy")).status_code == 200

    exercise(public_database, check)


def test_public_content_filters_profiles_services_links_and_settings(public_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        assert (await client.get(f"{BASE}/profile")).status_code == 404
        assert (await client.get(f"{BASE}/social-links")).json()["total"] == 0
        assert (await client.get(f"{BASE}/site-settings")).json() == []
        async with database.session() as session, session.begin():
            photo, cv = media(label="photo"), media("PDF", "cv")
            session.add_all([photo, cv])
            await session.flush()
            active = Profile(
                first_name="Ada", last_name="Lima", profile_media_id=photo.id, cv_media_id=cv.id
            )
            inactive = Profile(first_name="hidden-marker", last_name="Hidden", is_active=False)
            session.add_all([active, inactive])
            await session.flush()
            session.add_all(
                [
                    SocialLink(
                        profile_id=active.id,
                        platform="Web",
                        url="https://example.org",
                        sort_order=2,
                    ),
                    SocialLink(
                        profile_id=active.id,
                        platform="Blog",
                        url="https://example.org/blog",
                        sort_order=1,
                    ),
                    SocialLink(
                        profile_id=active.id,
                        platform="Hidden",
                        url="https://example.org/hidden",
                        is_visible=False,
                    ),
                    SocialLink(
                        profile_id=inactive.id, platform="Other", url="https://example.org/other"
                    ),
                    Service(name="Second", slug="second", sort_order=2),
                    Service(name="First", slug="first", sort_order=1),
                    Service(name="Hidden", slug="hidden", is_visible=False),
                    SiteSetting(key="site_title", value="Portfolio"),
                    SiteSetting(key="contact_enabled", value=False),
                    SiteSetting(key="jwt_secret_key", value="secret-marker"),
                ]
            )
        with select_count(database) as statements:
            response = await client.get(f"{BASE}/profile")
        assert len(statements) == 1
        assert response.status_code == 200, response.text
        assert response.json()["first_name"] == "Ada"
        assert response.json()["cv_media"]["type"] == "PDF"
        assert_public(response.json())
        for endpoint, key, first in (
            ("services", "slug", "first"),
            ("social-links", "platform", "Blog"),
        ):
            response = await client.get(f"{BASE}/{endpoint}?limit=1")
            assert response.status_code == 200
            assert response.json()["total"] == 2 and response.json()["items"][0][key] == first
            assert_public(response.json())
            assert (await client.get(f"{BASE}/{endpoint}?limit=1&offset=1")).json()["items"][0][
                key
            ] != first
        response = await client.get(f"{BASE}/site-settings")
        assert response.json() == [
            {"key": "contact_enabled", "value": False},
            {"key": "site_title", "value": "Portfolio"},
        ]
        assert_public(response.json())
        assert (
            "secret-marker" not in response.text and response.headers["Cache-Control"] == "no-store"
        )

    exercise(public_database, check)
