"""Check the ORM contract against the approved SQL without deploying a schema."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import DateTime, FetchedValue, create_mock_engine, inspect
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import (
    AppUser,
    Base,
    Category,
    MediaAsset,
    Profile,
    Project,
    ProjectCategory,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
    ProjectTag,
    RefreshToken,
    SiteSetting,
    SocialLink,
    Tag,
)

ROOT = Path(__file__).resolve().parents[1]
SQL = re.sub(r"--[^\n]*", "", (ROOT / "docs/database/schema.sql").read_text(encoding="utf-8"))
TABLES = dict(re.findall(r"CREATE TABLE (\w+\.\w+) \((.*?)\n\);", SQL, re.DOTALL))
DIALECT = create_mock_engine(
    "postgresql+psycopg://", lambda *args, **kwargs: None, json_serializer=json.dumps
).dialect


def normalize_sql(value: str) -> str:
    """Ignore formatting and keyword case while preserving quoted literal values."""
    tokens = re.findall(r"'(?:''|[^'])*'|\w+|[^\s]", value)
    return "".join(token if token.startswith("'") else token.lower() for token in tokens)


def test_registry_matches_both_design_documents() -> None:
    dbml = (ROOT / "docs/database/schema.dbml").read_text(encoding="utf-8")
    assert len(TABLES) == 18  # Original 17 domain tables plus the approved technical table.
    assert set(Base.metadata.tables) == set(TABLES) == set(re.findall(r"Table (\w+\.\w+)", dbml))
    assert {table.schema for table in Base.metadata.tables.values()} == {
        "auth",
        "portfolio",
        "media",
        "content",
        "contact",
    }


@pytest.mark.parametrize("table_name", TABLES)
def test_columns_types_nullability_and_defaults_match_sql(table_name: str) -> None:
    body = TABLES[table_name]
    declarations = re.findall(
        r"^    (\w+) (UUID|VARCHAR\(\d+\)|TEXT|BOOLEAN|TIMESTAMPTZ|SMALLINT|"
        r"NUMERIC\(\d+,\d+\)|INTEGER|BIGINT|JSONB|INET)([^\n]*)",
        body,
        re.MULTILINE,
    )
    table = Base.metadata.tables[table_name]
    assert list(table.c.keys()) == [name for name, _, _ in declarations]
    for name, sql_type, options in declarations:
        column = table.c[name]
        expected_type = "TIMESTAMP WITH TIME ZONE" if sql_type == "TIMESTAMPTZ" else sql_type
        assert normalize_sql(column.type.compile(dialect=DIALECT)) == normalize_sql(expected_type)
        assert column.nullable == ("NOT NULL" not in options and "PRIMARY KEY" not in options)
        expected_default = re.search(r"DEFAULT (.*?)(?:,)?$", options)
        if expected_default:
            assert column.server_default is not None
            assert normalize_sql(str(column.server_default.arg)) == normalize_sql(
                expected_default.group(1)
            )
        else:
            assert column.server_default is None
        assert column.default is None
        if isinstance(column.type, DateTime):
            assert column.type.timezone


@pytest.mark.parametrize("table_name", TABLES)
def test_constraints_and_primary_keys_match_sql(table_name: str) -> None:
    body = TABLES[table_name]
    table = Base.metadata.tables[table_name]
    expected = dict(re.findall(r"CONSTRAINT (\w+)\s+(.*?)(?=,\s*CONSTRAINT|$)", body, re.DOTALL))
    assert {constraint.name for constraint in table.constraints if constraint.name} == set(expected)
    ddl = normalize_sql(str(CreateTable(table).compile(dialect=DIALECT)))
    for name, definition in expected.items():
        assert normalize_sql(f"CONSTRAINT {name} {definition}") in ddl
    composite = re.search(r"PRIMARY KEY \(([^)]+)\)", body)
    expected_pk = [col.strip() for col in composite.group(1).split(",")] if composite else ["id"]
    assert list(table.primary_key.columns.keys()) == expected_pk


def test_all_indexes_match_sql_including_expressions_and_predicates() -> None:
    expected = {
        name: normalize_sql(statement)
        for statement, name in re.findall(
            r"(CREATE (?:UNIQUE )?INDEX (\w+)\s+ON .*?);", SQL, re.DOTALL
        )
    }
    actual = {
        index.name: normalize_sql(str(CreateIndex(index).compile(dialect=DIALECT)))
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert actual == expected


def test_all_foreign_keys_have_bidirectional_relationships() -> None:
    configure_mappers()
    mapped_foreign_keys: set[tuple[str, str]] = set()
    for mapper in Base.registry.mappers:
        for relation in mapper.relationships:
            assert relation.back_populates is not None
            inverse = relation.mapper.relationships[relation.back_populates]
            assert inverse.back_populates == relation.key
            assert relation.lazy == "raise"
            assert not relation.cascade.delete
            assert not relation.cascade.delete_orphan
            if relation.uselist:
                assert relation.passive_deletes == "all"
            else:
                for column in relation.local_columns:
                    assert column.foreign_keys
                    for fk in column.foreign_keys:
                        assert fk.column.table is relation.mapper.local_table
                        mapped_foreign_keys.add((column.table.fullname, column.name))
    expected = {
        (table.fullname, fk.parent.name)
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
    }
    assert len(expected) == 14
    assert mapped_foreign_keys == expected


def test_association_objects_synchronize_both_sides() -> None:
    project = Project(title="Courtyard", slug="courtyard")
    category = Category(name="Housing", slug="housing")
    category_link = ProjectCategory(project=project, category=category)
    assert project.category_links == category.project_links == [category_link]

    tag = Tag(name="Brick", slug="brick")
    tag_link = ProjectTag(project=project, tag=tag)
    assert project.tag_links == tag.project_links == [tag_link]

    asset = MediaAsset(type="IMAGE", asset_metadata={"credit": "Architect"})
    media_link = ProjectMedia(project=project, media_asset=asset, role="COVER")
    section = ProjectSection(project=project, section_type="IMAGE")
    section_link = ProjectSectionMedia(section=section, media_asset=asset)
    assert project.media_links == asset.project_links == [media_link]
    assert project.sections == [section]
    assert section.media_links == asset.section_links == [section_link]


def test_profile_media_foreign_keys_are_unambiguous() -> None:
    photo, cv = MediaAsset(type="IMAGE"), MediaAsset(type="PDF")
    profile = Profile(first_name="Ada", last_name="Lovelace", profile_media=photo, cv_media=cv)
    link = SocialLink(profile=profile, platform="Website", url="https://example.org")
    assert photo.photo_profiles == cv.cv_profiles == [profile]
    assert profile.social_links == [link]
    assert inspect(Profile).relationships.profile_media.local_columns == {
        Profile.__table__.c.profile_media_id
    }
    assert inspect(Profile).relationships.cv_media.local_columns == {
        Profile.__table__.c.cv_media_id
    }


def test_user_session_relationship() -> None:
    user = AppUser(email="architect@example.org", first_name="Ada", last_name="Lovelace")
    token = RefreshToken(user=user, token_hash="hashed-value")
    assert user.refresh_tokens == [token]


def test_json_mapping_preserves_reserved_metadata_and_null_semantics() -> None:
    assert MediaAsset.metadata is Base.metadata
    assert inspect(MediaAsset).attrs.asset_metadata.columns[0].name == "metadata"
    media_json = MediaAsset.__table__.c.metadata.type
    setting_json = SiteSetting.__table__.c.value.type
    media_bind = media_json.bind_processor(DIALECT)
    setting_bind = setting_json.bind_processor(DIALECT)
    assert media_bind is not None and setting_bind is not None
    assert media_bind(None) is None
    assert setting_bind(None) == "null"


def test_updated_at_marks_database_generated_values_without_creating_triggers() -> None:
    triggered_tables = set(re.findall(r"BEFORE UPDATE ON (\w+\.\w+)", SQL))
    marked_tables = set()
    for table in Base.metadata.tables.values():
        if "updated_at" in table.c:
            if table.fullname == "media.storage_operation":
                assert table.c.updated_at.server_onupdate is None  # Service owns intent timestamps.
                continue
            column = table.c.updated_at
            assert isinstance(column.server_onupdate, FetchedValue)
            assert column.onupdate is None
            marked_tables.add(table.fullname)
    assert marked_tables == triggered_tables


def test_registry_import_in_fresh_process_has_no_mapper_warnings() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers()",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
