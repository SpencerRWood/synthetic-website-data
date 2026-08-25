"""CSV export helpers."""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def export_csv(records: Iterable[dict[str, Any]], destination: str | Path) -> None:
    """Export records as CSV."""
    rows = list(records)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        if not rows:
            return
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
