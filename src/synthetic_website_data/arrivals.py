"""Non-homogeneous Poisson arrival generation."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from random import Random

from .config import SECONDS_PER_YEAR, WEEKDAY_NAMES, ArrivalsConfig

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
        if rng.random() <= effective_intensity(current, start, end, config):
            arrivals.append(current)

    return arrivals


def hourly_intensity(timestamp: datetime, config: ArrivalsConfig) -> float:
    """Return the configured intraday traffic intensity for a local timestamp."""
    return config.hourly_intensity[timestamp.hour]


def weekday_intensity(timestamp: datetime, config: ArrivalsConfig) -> float:
    """Return the recurring weekly traffic intensity for a local timestamp."""
    return config.weekday_intensity[WEEKDAY_NAMES[timestamp.weekday()]]


def trend_intensity(
    timestamp: datetime,
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
) -> float:
    """Return normalized linear annual trend intensity for ``timestamp``.

    Linear demand is ``1 + annual_growth_rate * elapsed_years``. Positive
    growth is normalized by the demand at ``end`` so the final point is 1.0;
    zero or negative growth is normalized by the start demand, so decline
    begins at 1.0 and falls linearly over elapsed calendar time.
    """
    rate = config.annual_growth_rate
    if rate == 0:
        return 1.0

    elapsed_years = (timestamp - start).total_seconds() / SECONDS_PER_YEAR
    demand = 1.0 + rate * elapsed_years
    if rate > 0:
        duration_years = (end - start).total_seconds() / SECONDS_PER_YEAR
        return demand / (1.0 + rate * duration_years)
    return demand


def effective_intensity(
    timestamp: datetime,
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
) -> float:
    """Return hourly x weekday x trend arrival intensity in ``[0, 1]``."""
    return (
        hourly_intensity(timestamp, config)
        * weekday_intensity(timestamp, config)
        * trend_intensity(timestamp, start, end, config)
    )


def arrival_rate_per_hour(
    timestamp: datetime,
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
) -> float:
    """Return the effective NHPP rate per hour bounded by the configured ceiling."""
    return config.maximum_rate_per_hour * effective_intensity(
        timestamp,
        start,
        end,
        config,
    )


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
