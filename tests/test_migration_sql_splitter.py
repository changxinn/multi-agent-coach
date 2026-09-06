"""Migration SQL statement parsing coverage."""

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