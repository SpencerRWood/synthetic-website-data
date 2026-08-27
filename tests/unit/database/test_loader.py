from pathlib import Path

import pytest

from synthetic_website_data.database import loader

VALID_CSV = (
    "event_id,visitor_id,session_id,page,timestamp\n"
    "019a1111-1111-7111-8111-111111111111,"
    "019a2222-2222-7222-8222-222222222222,"
    "019a3333-3333-7333-8333-333333333333,"
    "home,"
    "2026-01-01T09:00:00-05:00\n"
)


class PathLikeEventsCsv:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __fspath__(self) -> str:
        return str(self.path)


class FakeCopy:
    def __init__(self, operations: list[str], *, fail: bool = False) -> None:
        self.operations = operations
        self.fail = fail
        self.writes: list[str] = []

    def __enter__(self) -> FakeCopy:
        self.operations.append("copy_enter")
        return self

    def __exit__(self, *args: object) -> None:
        self.operations.append("copy_exit")

    def write(self, data: str) -> None:
        if self.fail:
            raise RuntimeError("copy failed")
        self.operations.append(f"write:{data.count('\n')}")
        self.writes.append(data)


class FakeCursor:
    rowcount = 1

    def __init__(self, operations: list[str], *, fail_copy: bool = False) -> None:
        self.operations = operations
        self.fail_copy = fail_copy

    def __enter__(self) -> FakeCursor:
        self.operations.append("cursor_enter")
        return self

    def __exit__(self, *args: object) -> None:
        self.operations.append("cursor_exit")

    def execute(self, sql: str) -> None:
        self.operations.append(sql)

    def copy(self, sql: str) -> FakeCopy:
        assert "COPY raw.events" in sql
        self.operations.append("copy")
        return FakeCopy(self.operations, fail=self.fail_copy)


class FakeConnection:
    def __init__(self, *, fail_copy: bool = False) -> None:
        self.operations: list[str] = []
        self.fail_copy = fail_copy

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.operations, fail_copy=self.fail_copy)

    def commit(self) -> None:
        self.operations.append("commit")

    def rollback(self) -> None:
        self.operations.append("rollback")

    def close(self) -> None:
        self.operations.append("close")


def write_events_csv(path: Path, content: str = VALID_CSV) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def patch_connection(
    monkeypatch: pytest.MonkeyPatch,
    connection: FakeConnection,
) -> FakeConnection:
    monkeypatch.setattr(loader, "connect", lambda: connection)
    return connection


def test_validate_events_csv_header_accepts_expected_header(tmp_path: Path) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")

    assert loader.validate_events_csv_header(csv_path) == loader.EXPECTED_EVENTS_HEADER


def test_load_events_csv_accepts_path_like_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")
    connection = patch_connection(monkeypatch, FakeConnection())

    row_count = loader.load_events_csv(PathLikeEventsCsv(csv_path))

    assert row_count == 1
    assert connection.operations[-2:] == ["commit", "close"]


def test_validate_events_csv_header_fails_for_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        loader.validate_events_csv_header(tmp_path / "missing.csv")


def test_validate_events_csv_header_fails_for_invalid_header(tmp_path: Path) -> None:
    csv_path = write_events_csv(
        tmp_path / "events.csv",
        "visitor_id,event_id,session_id,page,timestamp\n",
    )

    with pytest.raises(loader.CsvValidationError, match="invalid events header"):
        loader.validate_events_csv_header(csv_path)


def test_validate_events_csv_fails_for_naive_timestamp(tmp_path: Path) -> None:
    csv_path = write_events_csv(
        tmp_path / "events.csv",
        VALID_CSV.replace("2026-01-01T09:00:00-05:00", "2026-01-01T09:00:00"),
    )

    with pytest.raises(loader.CsvValidationError, match="naive timestamp"):
        loader.validate_events_csv(csv_path)


def test_replace_mode_truncates_before_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")
    connection = patch_connection(monkeypatch, FakeConnection())

    loader.load_events_csv(csv_path, replace=True)

    assert connection.operations.index(
        "TRUNCATE raw.events"
    ) < connection.operations.index("copy")


def test_replace_mode_reports_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")
    patch_connection(monkeypatch, FakeConnection())
    messages: list[str] = []

    loader.load_events_csv(csv_path, replace=True, progress=messages.append)

    assert messages == [
        f"Validating events CSV: {csv_path}",
        "Opening PostgreSQL connection",
        "Deleting old rows from raw.events",
        "Uploading events CSV with PostgreSQL COPY",
        "Committing database transaction",
    ]


def test_append_mode_does_not_truncate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")
    connection = patch_connection(monkeypatch, FakeConnection())

    loader.load_events_csv(csv_path)

    assert "TRUNCATE raw.events" not in connection.operations


def test_database_exception_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")
    connection = patch_connection(monkeypatch, FakeConnection(fail_copy=True))

    with pytest.raises(RuntimeError, match="copy failed"):
        loader.load_events_csv(csv_path, replace=True)

    assert "rollback" in connection.operations
    assert "commit" not in connection.operations
    assert connection.operations[-1] == "close"


def test_load_events_csv_streams_file_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(
        tmp_path / "events.csv",
        VALID_CSV + VALID_CSV.splitlines()[1],
    )
    connection = patch_connection(monkeypatch, FakeConnection())

    loader.load_events_csv(csv_path)

    writes = [
        operation
        for operation in connection.operations
        if operation.startswith("write:")
    ]
    assert len(writes) > 1


def test_copy_failure_is_not_hidden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = write_events_csv(tmp_path / "events.csv")
    patch_connection(monkeypatch, FakeConnection(fail_copy=True))

    with pytest.raises(RuntimeError, match="copy failed"):
        loader.load_events_csv(csv_path)


def test_copy_sql_uses_required_columns() -> None:
    for column in loader.EXPECTED_EVENTS_HEADER:
        assert column in loader.COPY_EVENTS_SQL
    assert "FORMAT CSV" in loader.COPY_EVENTS_SQL
    assert "HEADER TRUE" in loader.COPY_EVENTS_SQL
