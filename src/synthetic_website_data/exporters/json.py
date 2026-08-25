"""JSON export helpers."""

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID


def export_json(records: Iterable[dict[str, Any]], destination: str | Path) -> None:
    """Export records as JSON."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(list(records), default=_json_default, indent=2) + "\n",
        encoding="utf-8",
    )


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
