"""Non-homogeneous Poisson arrival generation."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from random import Random

from .config import ArrivalsConfig

SECONDS_PER_HOUR = 3600


def generate_arrivals(
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
    rng: Random,
) -> list[datetime]:
    """Generate ordered NHPP arrivals in ``[start, end)`` by thinning."""
    arrivals: list[datetime] = []

    for current in _homogeneous_arrivals(start, end, config.maximum_rate_per_hour, rng):
        if rng.random() <= config.hourly_intensity[current.hour]:
            arrivals.append(current)

    return arrivals


def _homogeneous_arrivals(
    start: datetime,
    end: datetime,
    maximum_rate_per_hour: float,
    rng: Random,
) -> Iterator[datetime]:
    current = start
    while True:
        delay_seconds = rng.expovariate(maximum_rate_per_hour / SECONDS_PER_HOUR)
        current += timedelta(seconds=delay_seconds)
        if current >= end:
            return
        yield current
