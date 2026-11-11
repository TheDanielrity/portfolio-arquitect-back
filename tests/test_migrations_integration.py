"""Migrations and database integrity verified in fresh disposable PostgreSQL databases."""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from ipaddress import ip_address
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import Base
from tests.migration_support import (
    REVISION,
    ROOT,
    catalog_snapshot,
    engine_for,
    in_transaction,
    migrate,
    temporary_databases,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migrated_database() -> Iterator[URL]:
    admin_url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not admin_url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL to create disposable migration test databases")

    async def initialize(migrated: URL, reference: URL) -> None:
        await migrate(migrated, "upgrade")
        first = await catalog_snapshot(migrated)
        assert len(first["tables"]) == 18
        assert len(first["triggers"]) == 10
        await migrate(migrated, "downgrade", "base")
        empty = await catalog_snapshot(migrated)
        for category in (
            "schemas",
            "tables",
            "columns",
            "constraints",
            "indexes",
            "triggers",
            "function",
        ):
            assert empty[category] == []
        assert empty["extension"] == [("pgcrypto",)]
        await migrate(migrated, "upgrade")
        assert await catalog_snapshot(migrated) == first

        engine = engine_for(reference)
        try:
            async with engine.begin() as connection:
                sql = (ROOT / "docs/database/schema.sql").read_text(encoding="utf-8")
                sql = sql.replace("\nBEGIN;", "").replace("\nCOMMIT;", "")
                await connection.exec_driver_sql(sql)
        finally:
            await engine.dispose()
        assert await catalog_snapshot(reference) == first
        await migrate(migrated, "check")

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(admin_url)
        migrated, reference = runner.run(databases.__aenter__())
        try:
            runner.run(initialize(migrated, reference))
            yield migrated
        finally:
            runner.run(databases.__aexit__(None, None, None))


async def add(connection: AsyncConnection, table_name: str, **values: object) -> UUID:
    table = Base.metadata.tables[table_name]
    result = await connection.execute(insert(table).values(**values).returning(table.c.id))
    value = result.scalar_one()
    assert isinstance(value, UUID)
    return value


async def asset(connection: AsyncConnection, **overrides: object) -> UUID:
    values: dict[str, object] = {
        "type": "IMAGE",
        "original_filename": "image.jpg",
        "storage_provider": "test",
        "storage_key": uuid4().hex,
        "url": "https://example.org/image.jpg",
        "mime_type": "image/jpeg",
        "file_size": 100,
    }
    return await add(connection, "media.media_asset", **(values | overrides))


async def reject(
    connection: AsyncConnection, table_name: str, constraint: str, **values: object
) -> None:
    with pytest.raises(IntegrityError) as error:
        async with connection.begin_nested():
            await connection.execute(insert(Base.metadata.tables[table_name]).values(**values))
    assert getattr(getattr(error.value.orig, "diag", None), "constraint_name", None) == constraint


def test_migration_roundtrip_matches_sql_and_is_at_head(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        assert (
            await connection.scalar(text("SELECT version_num FROM public.alembic_version"))
            == REVISION
        )

    in_transaction(migrated_database, check)


def test_email_uniqueness_and_refresh_token_rules(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        user = dict(
            email="Ada@Example.org", first_name="Ada", last_name="Lovelace", password_hash="hash"
        )
        user_id = await add(connection, "auth.app_user", **user)
        await reject(
            connection,
            "auth.app_user",
            "uq_app_user_email_lower",
            **(user | {"email": "ada@example.org"}),
        )
        token = dict(
            user_id=user_id, token_hash="hash", expires_at=datetime.now(UTC) + timedelta(days=1)
        )
        await add(connection, "auth.refresh_token", **token)
        await reject(connection, "auth.refresh_token", "uq_refresh_token_hash", **token)
        await reject(
            connection,
            "auth.refresh_token",
            "fk_refresh_token_user",
            **(token | {"user_id": uuid4(), "token_hash": "other"}),
        )

    in_transaction(migrated_database, check)


def test_soft_deleted_slug_reuse_and_restore_conflict(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        project_id = await add(connection, "portfolio.project", title="House", slug="house")
        await reject(
            connection, "portfolio.project", "uq_project_slug_active", title="Another", slug="house"
        )
        project = Base.metadata.tables["portfolio.project"]
        await connection.execute(
            update(project).where(project.c.id == project_id).values(deleted_at=datetime.now(UTC))
        )
        await add(connection, "portfolio.project", title="Replacement", slug="house")
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(
                    update(project).where(project.c.id == project_id).values(deleted_at=None)
                )

    in_transaction(migrated_database, check)


def test_single_cover_and_active_profile(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        project_id = await add(connection, "portfolio.project", title="House", slug="house")
        first, second = await asset(connection), await asset(connection)
        await add(
            connection,
            "portfolio.project_media",
            project_id=project_id,
            media_id=first,
            role="COVER",
        )
        await reject(
            connection,
            "portfolio.project_media",
            "uq_project_single_cover",
            project_id=project_id,
            media_id=second,
            role="COVER",
        )
        await add(
            connection,
            "portfolio.project_media",
            project_id=project_id,
            media_id=second,
            role="GALLERY",
        )
        await add(connection, "content.profile", first_name="Ada", last_name="Lovelace")
        await reject(
            connection,
            "content.profile",
            "uq_profile_single_active",
            first_name="Other",
            last_name="Person",
        )
        for _ in range(2):
            await add(
                connection,
                "content.profile",
                first_name="Inactive",
                last_name="Person",
                is_active=False,
            )

    in_transaction(migrated_database, check)


@pytest.mark.parametrize(
    ("table", "values", "constraint"),
    [
        (
            "portfolio.project",
            {"title": "House", "slug": "house", "status": "INVALID"},
            "ck_project_status",
        ),
        (
            "portfolio.project",
            {"title": "House", "slug": "house", "visibility": "INVALID"},
            "ck_project_visibility",
        ),
        ("portfolio.project", {"title": "House", "slug": "Bad Slug"}, "ck_project_slug_format"),
        ("portfolio.project", {"title": "House", "slug": "house", "year": 1799}, "ck_project_year"),
        ("portfolio.project", {"title": "House", "slug": "house", "area_m2": 0}, "ck_project_area"),
        (
            "portfolio.project",
            {"title": "House", "slug": "house", "sort_order": -1},
            "ck_project_sort_order",
        ),
        (
            "contact.contact_message",
            {"name": "Ada", "email": "a@example.org", "message": "Hi", "status": "INVALID"},
            "ck_contact_message_status",
        ),
        (
            "contact.contact_message",
            {"name": "Ada", "email": "a@example.org", "message": " "},
            "ck_contact_message_content",
        ),
    ],
)
def test_check_constraints(
    migrated_database: URL, table: str, values: dict[str, object], constraint: str
) -> None:
    async def check(connection: AsyncConnection) -> None:
        await reject(connection, table, constraint, **values)

    in_transaction(migrated_database, check)


def test_media_and_section_constraints(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        project_id = await add(connection, "portfolio.project", title="House", slug="house")
        media_id = await asset(connection)
        await reject(
            connection,
            "portfolio.project_media",
            "ck_project_media_role",
            project_id=project_id,
            media_id=media_id,
            role="INVALID",
        )
        await reject(
            connection,
            "portfolio.project_section",
            "ck_project_section_type",
            project_id=project_id,
            section_type="INVALID",
        )
        invalid_assets: list[tuple[dict[str, object], str]] = [
            ({"type": "INVALID"}, "ck_media_asset_type"),
            ({"width": 0}, "ck_media_asset_width"),
            ({"height": -1}, "ck_media_asset_height"),
            ({"file_size": -1}, "ck_media_asset_file_size"),
            ({"metadata": [1]}, "ck_media_asset_metadata_object"),
        ]
        for values, constraint in invalid_assets:
            with pytest.raises(IntegrityError) as error:
                async with connection.begin_nested():
                    await asset(connection, **values)
            assert (
                getattr(getattr(error.value.orig, "diag", None), "constraint_name", None)
                == constraint
            )
        await asset(connection, type="PDF", mime_type="application/pdf", width=None, height=None)

    in_transaction(migrated_database, check)


def test_foreign_key_delete_actions(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        project_id = await add(connection, "portfolio.project", title="House", slug="house")
        media_id = await asset(connection)
        await add(
            connection,
            "portfolio.project_media",
            project_id=project_id,
            media_id=media_id,
            role="COVER",
        )
        section_id = await add(
            connection, "portfolio.project_section", project_id=project_id, section_type="IMAGE"
        )
        section_media = Base.metadata.tables["portfolio.project_section_media"]
        await connection.execute(
            insert(section_media).values(section_id=section_id, media_id=media_id)
        )
        profile_id = await add(
            connection,
            "content.profile",
            first_name="Ada",
            last_name="Lovelace",
            profile_media_id=media_id,
            cv_media_id=media_id,
        )
        media = Base.metadata.tables["media.media_asset"]
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(media.delete().where(media.c.id == media_id))
        project = Base.metadata.tables["portfolio.project"]
        await connection.execute(project.delete().where(project.c.id == project_id))
        for name in ("project_media", "project_section", "project_section_media"):
            assert not (
                await connection.execute(select(Base.metadata.tables[f"portfolio.{name}"]))
            ).all()
        await connection.execute(media.delete().where(media.c.id == media_id))
        profile = Base.metadata.tables["content.profile"]
        row = (await connection.execute(select(profile).where(profile.c.id == profile_id))).one()
        assert row.profile_media_id is None and row.cv_media_id is None

    in_transaction(migrated_database, check)


def test_postgresql_values_defaults_and_updated_at_trigger(migrated_database: URL) -> None:
    async def check(connection: AsyncConnection) -> None:
        old = datetime(2000, 1, 1, tzinfo=UTC)
        project_id = await add(
            connection,
            "portfolio.project",
            title="House",
            slug="house",
            area_m2=Decimal("123.45"),
            updated_at=old,
        )
        project = Base.metadata.tables["portfolio.project"]
        row = (await connection.execute(select(project).where(project.c.id == project_id))).one()
        assert row.status == "DRAFT" and row.visibility == "PUBLIC"
        assert row.area_m2 == Decimal("123.45") and row.created_at.tzinfo is not None
        changed = (
            await connection.execute(
                update(project)
                .where(project.c.id == project_id)
                .values(title="Updated")
                .returning(project.c.updated_at)
            )
        ).scalar_one()
        assert changed > old
        contact_id = await add(
            connection,
            "contact.contact_message",
            name="Ada",
            email="a@example.org",
            message="Hi",
            ip_address=ip_address("2001:db8::1"),
        )
        contact = Base.metadata.tables["contact.contact_message"]
        assert await connection.scalar(
            select(contact.c.ip_address).where(contact.c.id == contact_id)
        ) == ip_address("2001:db8::1")
        await add(connection, "content.site_setting", key="test", value={"nested": [1, True, None]})

    in_transaction(migrated_database, check)
