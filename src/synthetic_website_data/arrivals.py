"""Non-homogeneous Poisson arrival generation."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random

from .campaigns import (
    CampaignEffect,
    CampaignSchedule,
    campaign_incremental_rate_per_hour,
    maximum_campaign_rate_per_hour,
)
from .config import SECONDS_PER_YEAR, WEEKDAY_NAMES, ArrivalsConfig, CampaignConfig

SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class Arrival:
    timestamp: datetime
    campaign_id: str | None = None
    channel: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


def generate_arrivals(
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
    rng: Random,
) -> list[datetime]:
    """Generate ordered NHPP arrival timestamps in ``[start, end)`` by thinning."""
    return [
        arrival.timestamp
        for arrival in generate_arrival_records(
            start=start,
            end=end,
            config=config,
            rng=rng,
        )
    ]


def generate_arrival_records(
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
    rng: Random,
    campaigns: tuple[CampaignConfig, ...] = (),
) -> list[Arrival]:
    """Generate ordered NHPP arrivals with optional campaign provenance."""
    arrivals: list[Arrival] = []
    maximum_rate = config.maximum_rate_per_hour + maximum_campaign_rate_per_hour(
        campaigns
    )
    campaign_schedule = CampaignSchedule.build(campaigns, start, end)

    for current in _homogeneous_arrivals(start, end, maximum_rate, rng):
        baseline_rate = arrival_rate_per_hour(current, start, end, config)
        campaign_effects = campaign_schedule.effects_for_day(current.date())
        campaign_rate = campaign_schedule.incremental_rate_per_hour(current)
        rate = baseline_rate + campaign_rate
        if rng.random() <= rate / maximum_rate:
            arrivals.append(
                Arrival(
                    timestamp=current,
                    **_choose_campaign_source(
                        baseline_rate,
                        campaign_effects,
                        rng,
                    ),
                )
            )

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


def combined_arrival_rate_per_hour(
    timestamp: datetime,
    start: datetime,
    end: datetime,
    config: ArrivalsConfig,
    campaigns: tuple[CampaignConfig, ...] = (),
) -> float:
    """Return baseline plus additive campaign-driven visitor arrival rate."""
    return arrival_rate_per_hour(timestamp, start, end, config) + (
        campaign_incremental_rate_per_hour(timestamp, campaigns, start, end)
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


def _choose_campaign_source(
    baseline_rate: float,
    effects: tuple[CampaignEffect, ...],
    rng: Random,
) -> dict[str, str | None]:
    """Select direct campaign provenance for an accepted arrival.

    Carryover lift still increases the arrival rate, but it represents users
    returning because they remember a past campaign rather than a current ad
    interaction.  Only effects with spend on the arrival day receive campaign
    and UTM provenance.
    """
    total_rate = baseline_rate + sum(
        effect.incremental_visitors / 24.0 for effect in effects
    )
    if total_rate <= 0:
        return _empty_campaign_source()

    attributable_effects = tuple(effect for effect in effects if effect.daily_spend > 0)
    unattributed_rate = baseline_rate + sum(
        effect.incremental_visitors / 24.0
        for effect in effects
        if effect.daily_spend == 0
    )

    threshold = rng.random() * total_rate
    if threshold < unattributed_rate:
        return _empty_campaign_source()

    cumulative = unattributed_rate
    for effect in attributable_effects:
        cumulative += effect.incremental_visitors / 24.0
        if threshold <= cumulative:
            return {
                "campaign_id": effect.campaign_id,
                "channel": effect.channel,
                "utm_source": effect.utm_source,
                "utm_medium": effect.utm_medium,
                "utm_campaign": effect.utm_campaign,
            }
    return _empty_campaign_source()


def _empty_campaign_source() -> dict[str, str | None]:
    return {
        "campaign_id": None,
        "channel": None,
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
    }
