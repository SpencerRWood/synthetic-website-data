"""Bulk-load generated event CSVs into PostgreSQL."""

import csv
from collections.abc import Callable
from datetime import datetime
from os import PathLike
from pathlib import Path

from synthetic_website_data.database.connection import connect

EXPECTED_EVENTS_HEADER = (
    "event_id",
    "visitor_id",
    "session_id",
    "page",
    "timestamp",
)

COPY_EVENTS_SQL = """
COPY raw.events (
    event_id,
    visitor_id,
    session_id,
    page,
    timestamp
)
FROM STDIN
WITH (
    FORMAT CSV,
    HEADER TRUE
)
"""


class CsvValidationError(ValueError):
    """Raised when an events CSV cannot be loaded safely."""


def _validate_timestamp(timestamp: str, *, path: Path, line_number: int) -> None:
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
    except ValueError as error:
        raise CsvValidationError(
            f"{path} line {line_number} has invalid timestamp {timestamp!r}."
        ) from error

    if (
        parsed_timestamp.tzinfo is None
        or parsed_timestamp.tzinfo.utcoffset(parsed_timestamp) is None
    ):
        raise CsvValidationError(
            f"{path} line {line_number} has naive timestamp {timestamp!r}; "
            "expected timezone-aware timestamp text."
        )


def validate_events_csv(csv_path: str | PathLike[str]) -> tuple[str, ...]:
    """Validate the events CSV shape needed before database mutation."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        try:
            header = tuple(next(reader))
        except StopIteration as error:
            raise CsvValidationError(
                f"{path} is empty; expected an events header."
            ) from error

        if header != EXPECTED_EVENTS_HEADER:
            expected = ",".join(EXPECTED_EVENTS_HEADER)
            actual = ",".join(header) if header else "<missing>"
            raise CsvValidationError(
                f"{path} has invalid events header {actual!r}; expected {expected!r}."
            )

        dict_reader = csv.DictReader(file, fieldnames=header)
        for line_number, row in enumerate(dict_reader, start=2):
            _validate_timestamp(
                row["timestamp"],
                path=path,
                line_number=line_number,
            )

    return header


def validate_events_csv_header(csv_path: str | PathLike[str]) -> tuple[str, ...]:
    """Validate and return the header from an events CSV."""
    return validate_events_csv(csv_path)


def load_events_csv(
    csv_path: str | PathLike[str],
    *,
    replace: bool = False,
    progress: Callable[[str], None] | None = None,
) -> int:
    """Load a generated events CSV into raw.events with PostgreSQL COPY.

    Returns psycopg's COPY row count when available. psycopg/PostgreSQL perform
    UUID, timestamp, nullability, primary-key, and table-existence validation.
    """
    path = Path(csv_path)
    if progress is not None:
        progress(f"Validating events CSV: {path}")
    validate_events_csv(path)

    if progress is not None:
        progress("Opening PostgreSQL connection")
    connection = connect()
    try:
        with connection.cursor() as cursor:
            if replace:
                if progress is not None:
                    progress("Deleting old rows from raw.events")
                cursor.execute("TRUNCATE raw.events")

            if progress is not None:
                progress("Uploading events CSV with PostgreSQL COPY")
            with (
                path.open("r", encoding="utf-8", newline="") as file,
                cursor.copy(COPY_EVENTS_SQL) as copy,
            ):
                for chunk in file:
                    copy.write(chunk)

            row_count = cursor.rowcount

        if progress is not None:
            progress("Committing database transaction")
        connection.commit()
    except Exception:
        if progress is not None:
            progress("Rolling back database transaction")
        connection.rollback()
        raise
    finally:
        connection.close()

    return int(row_count) if row_count is not None else -1


def _load_events_csv_from_args(argv: list[str]) -> int:
    if not argv or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--replace"):
        raise SystemExit(
            "usage: python -m synthetic_website_data.database path/to/events.csv "
            "[--replace]"
        )
    return load_events_csv(argv[0], replace="--replace" in argv)
