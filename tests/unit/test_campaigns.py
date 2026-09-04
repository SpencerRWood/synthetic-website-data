from dataclasses import replace
from datetime import datetime
from random import Random
from zoneinfo import ZoneInfo

import pytest

from synthetic_website_data.arrivals import (
    combined_arrival_rate_per_hour,
    generate_arrival_records,
)
from synthetic_website_data.campaigns import (
    campaign_effects_for_day,
    daily_campaign_effects,
    geometric_adstock,
    saturated_response,
)
from synthetic_website_data.config import CampaignConfig, GeneratorConfig, parse_config
from synthetic_website_data.generators import generate_dataset

TZ = ZoneInfo("America/New_York")


def campaign(**overrides: object) -> CampaignConfig:
    values = {
        "campaign_id": "paid_search_jan",
        "channel": "paid_search",
        "start": "2026-01-01T00:00:00",
        "end": "2026-01-02T00:00:00",
        "daily_spend": 100.0,
        "adstock_decay": 0.5,
        "saturation": 100.0,
        "maximum_visitor_lift": 240.0,
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "paid_search_jan",
    } | overrides
    return CampaignConfig(
        campaign_id=str(values["campaign_id"]),
        channel=str(values["channel"]),
        start=datetime.fromisoformat(str(values["start"])).replace(tzinfo=TZ),
        end=datetime.fromisoformat(str(values["end"])).replace(tzinfo=TZ),
        daily_spend=_float_value(values["daily_spend"]),
        adstock_decay=_float_value(values["adstock_decay"]),
        saturation=_float_value(values["saturation"]),
        maximum_visitor_lift=_float_value(values["maximum_visitor_lift"]),
        utm_source=str(values["utm_source"]),
        utm_medium=str(values["utm_medium"]),
        utm_campaign=str(values["utm_campaign"]),
    )


def _float_value(value: object) -> float:
    if not isinstance(value, int | float | str):
        raise TypeError("campaign helper values must be numeric")
    return float(value)


def traffic_config(
    *,
    start_date: str = "2026-01-05T00:00:00",
    end_date: str = "2026-01-12T00:00:00",
) -> GeneratorConfig:
    raw = {
        "dataset": {
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "America/New_York",
            "random_seed": 42,
        },
        "website": {
            "entry_page": "home",
            "terminal_pages": ["checkout"],
            "graph": {
                "home": {"checkout": 1.0},
                "checkout": {},
            },
        },
        "arrivals": {
            "maximum_rate_per_hour": 100,
            "annual_growth_rate": 0.0,
            "hourly_intensity": dict.fromkeys(range(24), 0.25),
            "weekday_intensity": {
                "monday": 1.0,
                "tuesday": 0.95,
                "wednesday": 0.9,
                "thursday": 0.85,
                "friday": 0.8,
                "saturday": 0.45,
                "sunday": 0.35,
            },
        },
        "sessions": {
            "drop_off_probability": 0.0,
            "max_page_views": 30,
        },
        "page_views": {
            "delay": {
                "distribution": "gamma",
                "shape": 2.0,
                "scale_seconds": 0.001,
            },
        },
    }
    return parse_config(raw)


def test_geometric_adstock_applies_decay_carryover() -> None:
    assert geometric_adstock([100.0, 50.0, 0.0], decay=0.5) == [
        100.0,
        100.0,
        50.0,
    ]


def test_saturation_curve_bounds_adstock_response() -> None:
    assert saturated_response(0.0, saturation=100.0) == 0.0
    assert saturated_response(100.0, saturation=100.0) == 0.5
    assert saturated_response(300.0, saturation=100.0) == 0.75


def test_overlapping_campaigns_have_additive_effects() -> None:
    dataset_start = datetime(2026, 1, 1, tzinfo=TZ)
    dataset_end = datetime(2026, 1, 4, tzinfo=TZ)
    paid_search = campaign(campaign_id="paid_search", maximum_visitor_lift=240.0)
    display = campaign(
        campaign_id="display",
        channel="display",
        maximum_visitor_lift=120.0,
    )

    effects = campaign_effects_for_day(
        (paid_search, display),
        datetime(2026, 1, 1, tzinfo=TZ).date(),
        dataset_start,
        dataset_end,
    )

    assert {effect.campaign_id for effect in effects} == {"paid_search", "display"}
    assert sum(effect.incremental_visitors for effect in effects) == 180.0


def test_campaign_end_date_allows_adstock_carryover_without_spend() -> None:
    effects = daily_campaign_effects(
        campaign(end="2026-01-01T00:00:00"),
        datetime(2026, 1, 1, tzinfo=TZ).date(),
        datetime(2026, 1, 4, tzinfo=TZ).date(),
    )

    assert effects[datetime(2026, 1, 1, tzinfo=TZ).date()].adstock == 100.0
    assert effects[datetime(2026, 1, 2, tzinfo=TZ).date()].adstock == 50.0
    assert effects[datetime(2026, 1, 3, tzinfo=TZ).date()].adstock == 25.0


def test_campaign_effects_integrate_with_visitor_arrival_rate() -> None:
    config = traffic_config(
        start_date="2026-01-01T12:00:00",
        end_date="2026-01-02T12:00:00",
    )
    config.arrivals.hourly_intensity[12] = 1.0
    timestamp = datetime(2026, 1, 1, 12, tzinfo=TZ)

    baseline_rate = combined_arrival_rate_per_hour(
        timestamp,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )
    campaign_rate = combined_arrival_rate_per_hour(
        timestamp,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
        (campaign(),),
    )

    assert campaign_rate == pytest.approx(baseline_rate + 5.0)


def test_campaign_provenance_is_available_on_campaign_arrivals() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2026-01-01T03:00:00",
    )
    records = generate_arrival_records(
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
        Random(7),  # noqa: S311
        campaigns=(
            campaign(
                daily_spend=10_000.0,
                saturation=1.0,
                maximum_visitor_lift=50_000.0,
            ),
        ),
    )

    assert any(record.campaign_id == "paid_search_jan" for record in records)
    assert any(record.channel == "paid_search" for record in records)


def test_carryover_arrivals_generate_users_without_campaign_pageview_properties() -> (
    None
):
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2026-01-03T00:00:00",
    )
    config = replace(
        config,
        arrivals=replace(
            config.arrivals,
            maximum_rate_per_hour=0.001,
            hourly_intensity=dict.fromkeys(range(24), 0.0),
        ),
        campaigns=(
            campaign(
                end="2026-01-01T00:00:00",
                daily_spend=100.0,
                saturation=1.0,
                maximum_visitor_lift=24.0,
            ),
        ),
    )

    dataset = generate_dataset(config)
    carryover_sessions = [
        session
        for session in dataset.sessions
        if session.session_start_time.date() == datetime(2026, 1, 2, tzinfo=TZ).date()
    ]

    assert carryover_sessions
    for session in carryover_sessions:
        assert session.campaign_id is None
        for event in session.events:
            assert "campaign_id" not in event.properties
            assert "channel" not in event.properties
            assert "utm_source" not in event.properties
            assert "utm_medium" not in event.properties
            assert "utm_campaign" not in event.properties


def test_campaign_pageviews_include_utm_properties() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2026-01-01T03:00:00",
    )
    raw = {
        "dataset": {
            "start_date": config.dataset.start.isoformat(),
            "end_date": config.dataset.end.isoformat(),
            "timezone": "America/New_York",
            "random_seed": 7,
        },
        "website": {
            "entry_page": "home",
            "terminal_pages": ["checkout"],
            "graph": {
                "home": {"checkout": 1.0},
                "checkout": {},
            },
        },
        "arrivals": {
            "maximum_rate_per_hour": 1,
            "annual_growth_rate": 0.0,
            "hourly_intensity": dict.fromkeys(range(24), 0.0),
            "weekday_intensity": {
                "monday": 1.0,
                "tuesday": 1.0,
                "wednesday": 1.0,
                "thursday": 1.0,
                "friday": 1.0,
                "saturday": 1.0,
                "sunday": 1.0,
            },
        },
        "campaigns": [
            {
                "campaign_id": "summer_search",
                "channel": "paid_search",
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign": "summer_search",
                "start_date": "2026-01-01",
                "end_date": "2026-01-01",
                "daily_spend": 10_000.0,
                "adstock_decay": 0.0,
                "saturation": 1.0,
                "maximum_visitor_lift": 50_000.0,
            }
        ],
        "sessions": {
            "drop_off_probability": 0.0,
            "max_page_views": 30,
        },
        "page_views": {
            "delay": {
                "distribution": "gamma",
                "shape": 2.0,
                "scale_seconds": 0.001,
            },
        },
    }

    dataset = generate_dataset(parse_config(raw))
    pageview = dataset.sessions[0].events[0]

    assert pageview.properties["utm_source"] == "google"
    assert pageview.properties["utm_medium"] == "cpc"
    assert pageview.properties["utm_campaign"] == "summer_search"
    assert pageview.properties["campaign_id"] == "summer_search"
    assert pageview.properties["channel"] == "paid_search"
