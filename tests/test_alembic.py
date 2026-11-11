from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command, context


def test_alembic_has_one_initial_revision() -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0003_single_featured"]
    assert script.get_revision("head").down_revision == "0002_storage_operations"
    assert script.get_revision("0001_initial_schema").down_revision is None
    assert (Path(script.dir) / "script.py.mako").is_file()


def test_alembic_offline_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:p%40ss%25word@localhost:5432/test"
    )
    root = Path(__file__).resolve().parents[1]
    output = StringIO()
    config = Config(str(root / "alembic.ini"), output_buffer=output)
    with patch("alembic.context.configure", wraps=context.configure) as configure:
        command.upgrade(config, "head", sql=True)
    options = configure.call_args.kwargs
    assert options["include_schemas"] is True
    assert options["version_table_schema"] == "public"
    assert len(options["target_metadata"].tables) == 18
    for schema in ("auth", "portfolio", "media", "content", "contact"):
        assert options["include_name"](schema, "schema", {})
    for excluded_schema in (None, "public", "unrelated"):
        assert not options["include_name"](excluded_schema, "schema", {})
    sql = output.getvalue()
    assert "BEGIN" in sql
    assert "COMMIT" in sql
    assert sql.count("CREATE TABLE") == 19  # Domain, technical and alembic_version tables.
    assert sql.count("CREATE TRIGGER") == 10
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in sql
    assert "CREATE FUNCTION public.set_updated_at()" in sql
    assert "p%40ss" not in sql


def test_revision_template_renders(tmp_path: Path) -> None:
    import shutil

    root = Path(__file__).resolve().parents[1]
    scripts = tmp_path / "migrations"
    (scripts / "versions").mkdir(parents=True)
    shutil.copyfile(root / "alembic/script.py.mako", scripts / "script.py.mako")
    config = Config()
    config.set_main_option("script_location", str(scripts))
    command.revision(config, message="Template validation", rev_id="test_revision")
    generated = next((scripts / "versions").glob("*.py"))
    compile(generated.read_text(encoding="utf-8"), str(generated), "exec")


def test_offline_downgrade_is_explicit_and_preserves_shared_extension() -> None:
    root = Path(__file__).resolve().parents[1]
    output = StringIO()
    config = Config(str(root / "alembic.ini"), output_buffer=output)
    command.downgrade(config, "0001_initial_schema:base", sql=True)
    sql = output.getvalue()
    assert sql.count("DROP TABLE") == 17
    assert "DELETE FROM public.alembic_version" in sql
    assert sql.count("DROP SCHEMA") == 5
    assert "DROP FUNCTION public.set_updated_at()" in sql
    assert "CASCADE" not in sql
    assert "DROP EXTENSION" not in sql
