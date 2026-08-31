"""CSV export helpers."""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def export_csv(records: Iterable[dict[str, Any]], destination: str | Path) -> None:
    """Export records as CSV."""
    export_csv_with_fields(records, destination)


def export_csv_with_fields(
    records: Iterable[dict[str, Any]],
    destination: str | Path,
    fieldnames: list[str] | None = None,
) -> None:
    """Export records as CSV with optional explicit fieldnames."""
    rows = list(records)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        if not rows and fieldnames is None:
            return
        writer = csv.DictWriter(file, fieldnames=fieldnames or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
