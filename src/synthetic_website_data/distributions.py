"""Small distribution helpers used by the website simulator."""

import csv
from dataclasses import dataclass
from pathlib import Path
from random import Random

from .config import ConfigurationError


@dataclass(frozen=True)
class GeographyRecord:
    zip_code: str
    state: str
    area_code: str
    population: int


@dataclass(frozen=True)
class GeographyDistribution:
    records: tuple[GeographyRecord, ...]
    weights: tuple[float, ...]

    def sample(self, rng: Random) -> GeographyRecord:
        return sample_weighted(self.records, self.weights, rng)


def sample_weighted[T](
    items: tuple[T, ...],
    weights: tuple[float, ...],
    rng: Random,
) -> T:
    """Sample an item according to non-normalized non-negative weights."""
    if len(items) != len(weights):
        raise ValueError("items and weights must have the same length")
    if not items:
        raise ValueError("items must not be empty")

    total = sum(weights)
    if total <= 0:
        raise ValueError("at least one weight must be positive")

    threshold = rng.random() * total
    cumulative = 0.0
    last_item = items[-1]
    for item, weight in zip(items, weights, strict=True):
        if weight < 0:
            raise ValueError("weights must be non-negative")
        cumulative += weight
        if threshold <= cumulative:
            return item
    return last_item


def sample_weighted_category(weights: dict[str, float], rng: Random) -> str:
    """Sample a categorical value from non-normalized weights."""
    return sample_weighted(tuple(weights), tuple(weights.values()), rng)


def sample_normal(mean: float, standard_deviation: float, rng: Random) -> float:
    """Sample from a normal distribution with the provided RNG."""
    if standard_deviation < 0:
        raise ValueError("standard_deviation must be non-negative")
    return rng.gauss(mean, standard_deviation)


def load_geography_distribution(path: str | Path) -> GeographyDistribution:
    """Load population-weighted ZIP/state/area-code reference data."""
    distribution_path = Path(path)
    if not distribution_path.is_file():
        raise ConfigurationError(
            f"visitor_profile.geography.distribution_file does not exist: "
            f"{distribution_path}"
        )

    records: list[GeographyRecord] = []
    with distribution_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {"zip_code", "state", "area_code", "population"}
        if reader.fieldnames is None:
            raise ConfigurationError("geography distribution must have a header")
        missing = required_columns.difference(reader.fieldnames)
        if missing:
            missing_columns = ", ".join(sorted(missing))
            raise ConfigurationError(
                f"geography distribution missing required columns: {missing_columns}"
            )

        for line_number, row in enumerate(reader, start=2):
            records.append(_parse_geography_record(row, line_number, distribution_path))

    if not records:
        raise ConfigurationError("geography distribution must include at least one row")
    if sum(record.population for record in records) <= 0:
        raise ConfigurationError(
            "geography distribution must include positive population weight"
        )

    return GeographyDistribution(
        records=tuple(records),
        weights=tuple(float(record.population) for record in records),
    )


def _parse_geography_record(
    row: dict[str, str],
    line_number: int,
    path: Path,
) -> GeographyRecord:
    zip_code = row["zip_code"].strip()
    state = row["state"].strip().upper()
    area_code = row["area_code"].strip()
    if len(zip_code) != 5 or not zip_code.isdigit():
        raise ConfigurationError(
            f"{path} line {line_number} has invalid zip_code {zip_code!r}"
        )
    if len(state) != 2 or not state.isalpha():
        raise ConfigurationError(
            f"{path} line {line_number} has invalid state {state!r}"
        )
    if len(area_code) != 3 or not area_code.isdigit():
        raise ConfigurationError(
            f"{path} line {line_number} has invalid area_code {area_code!r}"
        )
    try:
        population = int(row["population"])
    except ValueError as error:
        raise ConfigurationError(
            f"{path} line {line_number} has invalid population"
        ) from error
    if population < 0:
        raise ConfigurationError(
            f"{path} line {line_number} population must be non-negative"
        )
    if not zip_code or not state:
        raise ConfigurationError(
            f"{path} line {line_number} zip_code and state are required"
        )
    return GeographyRecord(
        zip_code=zip_code,
        state=state,
        area_code=area_code,
        population=population,
    )
