"""Campaign adstock and visitor-rate effects."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .config import CampaignConfig


@dataclass(frozen=True)
class CampaignEffect:
    campaign_id: str
    channel: str
    date_day: date
    daily_spend: float
    adstock: float
    saturated_demand: float
    incremental_visitors: float
    utm_source: str
    utm_medium: str
    utm_campaign: str


@dataclass(frozen=True)
class CampaignSchedule:
    effects_by_day: dict[date, tuple[CampaignEffect, ...]]

    @classmethod
    def build(
        cls,
        campaigns: tuple[CampaignConfig, ...],
        dataset_start: datetime,
        dataset_end: datetime,
    ) -> CampaignSchedule:
        start_date = dataset_start.date()
        end_date = dataset_end.date() + timedelta(days=1)
        effects_by_day: dict[date, list[CampaignEffect]] = {}
        for campaign in campaigns:
            for day, effect in daily_campaign_effects(
                campaign,
                start_date,
                end_date,
            ).items():
                if effect.incremental_visitors > 0:
                    effects_by_day.setdefault(day, []).append(effect)
        return cls(
            effects_by_day={
                day: tuple(effects) for day, effects in effects_by_day.items()
            }
        )

    def effects_for_day(self, day: date) -> tuple[CampaignEffect, ...]:
        return self.effects_by_day.get(day, ())

    def incremental_rate_per_hour(self, timestamp: datetime) -> float:
        return (
            sum(
                effect.incremental_visitors
                for effect in self.effects_for_day(timestamp.date())
            )
            / 24.0
        )


def geometric_adstock(spend: list[float], decay: float) -> list[float]:
    """Return geometric adstock where each day carries over prior demand."""
    adstock: list[float] = []
    previous = 0.0
    for value in spend:
        current = value + decay * previous
        adstock.append(current)
        previous = current
    return adstock


def saturated_response(adstock: float, saturation: float) -> float:
    """Return a simple saturating response in ``[0, 1)``."""
    if adstock <= 0:
        return 0.0
    return adstock / (adstock + saturation)


def daily_campaign_effects(
    campaign: CampaignConfig,
    start_date: date,
    end_date: date,
) -> dict[date, CampaignEffect]:
    """Return daily adstock and lift for ``[start_date, end_date)``."""
    days = _date_range(start_date, end_date)
    spend = [
        campaign.daily_spend if _campaign_spends_on(campaign, day) else 0.0
        for day in days
    ]
    adstock_values = geometric_adstock(spend, campaign.adstock_decay)

    effects: dict[date, CampaignEffect] = {}
    for day, day_spend, adstock in zip(days, spend, adstock_values, strict=True):
        saturated = saturated_response(adstock, campaign.saturation)
        effects[day] = CampaignEffect(
            campaign_id=campaign.campaign_id,
            channel=campaign.channel,
            date_day=day,
            daily_spend=day_spend,
            adstock=adstock,
            saturated_demand=saturated,
            incremental_visitors=campaign.maximum_visitor_lift * saturated,
            utm_source=campaign.utm_source,
            utm_medium=campaign.utm_medium,
            utm_campaign=campaign.utm_campaign,
        )
    return effects


def campaign_effects_for_day(
    campaigns: tuple[CampaignConfig, ...],
    day: date,
    dataset_start: datetime,
    dataset_end: datetime,
) -> list[CampaignEffect]:
    """Return all campaign effects active through spend or carryover for a day."""
    schedule = CampaignSchedule.build(campaigns, dataset_start, dataset_end)
    return list(schedule.effects_for_day(day))


def campaign_incremental_rate_per_hour(
    timestamp: datetime,
    campaigns: tuple[CampaignConfig, ...],
    dataset_start: datetime,
    dataset_end: datetime,
) -> float:
    """Return additive campaign-driven visitor demand as an hourly rate."""
    schedule = CampaignSchedule.build(campaigns, dataset_start, dataset_end)
    return schedule.incremental_rate_per_hour(timestamp)


def maximum_campaign_rate_per_hour(campaigns: tuple[CampaignConfig, ...]) -> float:
    """Return a conservative hourly ceiling for thinning combined arrivals."""
    return sum(campaign.maximum_visitor_lift for campaign in campaigns) / 24.0


def _campaign_spends_on(campaign: CampaignConfig, day: date) -> bool:
    return campaign.start.date() <= day <= campaign.end.date()


def _date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current < end:
        days.append(current)
        current += timedelta(days=1)
    return days
