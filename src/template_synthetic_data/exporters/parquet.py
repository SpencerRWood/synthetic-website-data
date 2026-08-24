"""Parquet export placeholders."""

from collections.abc import Iterable
from typing import Any


def export_parquet(_records: Iterable[dict[str, Any]], _destination: str) -> None:
    """Export records as Parquet."""
    # TODO: Implement Parquet dataset export.
    raise NotImplementedError
