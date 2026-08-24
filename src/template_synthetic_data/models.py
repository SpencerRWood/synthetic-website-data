"""Synthetic data model placeholders."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticRecord:
    """Placeholder synthetic record wrapper."""

    values: dict[str, object]
