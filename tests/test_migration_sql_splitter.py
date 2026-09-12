"""Migration SQL statement parsing coverage."""

from pathlib import Path

from app.db.migrate import _migration_statements


def test_migration_statements_preserve_semicolons_inside_sql_quotes() -> None:
    assert _migration_statements(
        "CREATE TABLE example (value TEXT DEFAULT ';'); INSERT INTO example VALUES ('a;b');"
    ) == [
        "CREATE TABLE example (value TEXT DEFAULT ';')",
        "INSERT INTO example VALUES ('a;b')",
    ]


def test_migration_statements_ignore_semicolons_inside_line_comments() -> None:
    assert _migration_statements("-- comment; ignored\nCREATE TABLE example (id INT);") == [
        "-- comment; ignored\nCREATE TABLE example (id INT)"
    ]


def test_migration_statements_preserve_postgres_dollar_quoted_function_body() -> None:
    function = """CREATE FUNCTION example() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'rows are immutable';
END;
$$ LANGUAGE plpgsql"""
    assert _migration_statements(f"{function}; CREATE TRIGGER example_trigger;") == [
        function,
        "CREATE TRIGGER example_trigger",
    ]


def test_migration_statements_preserve_tagged_postgres_dollar_quoted_body() -> None:
    function = "CREATE FUNCTION example() RETURNS text AS $body$ BEGIN RETURN 'a;b'; END; $body$ LANGUAGE plpgsql"
    assert _migration_statements(f"{function}; SELECT 1;") == [function, "SELECT 1"]


def test_migration_011_keeps_immutable_trigger_function_intact() -> None:
    migration_path = Path(__file__).parents[1] / "app/db/migrations/011_create_chat_history_tables.sql"
    statements = _migration_statements(migration_path.read_text(encoding="utf-8"))

    function = next(statement for statement in statements if "CREATE FUNCTION" in statement)
    assert "RAISE EXCEPTION 'chat_messages are immutable';" in function
    assert "$$ LANGUAGE plpgsql" in function


def test_migration_013_preserves_cascade_only_immutable_trigger_exception() -> None:
    migration_path = Path(__file__).parents[1] / "app/db/migrations/013_allow_chat_message_cascade_deletion.sql"
    statements = _migration_statements(migration_path.read_text(encoding="utf-8"))

    assert len(statements) == 1
    assert "pg_trigger_depth() > 1" in statements[0]
    assert "RAISE EXCEPTION 'chat_messages are immutable';" in statements[0]