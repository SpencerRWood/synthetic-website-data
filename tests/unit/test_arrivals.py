from datetime import datetime
from random import Random
from zoneinfo import ZoneInfo

from synthetic_website_data.arrivals import (
    arrival_rate_per_hour,
    effective_intensity,
    generate_arrivals,
    hourly_intensity,
    trend_intensity,
    weekday_intensity,
)
from synthetic_website_data.config import GeneratorConfig, parse_config


def traffic_config(
    *,
    start_date: str = "2026-01-05T00:00:00",
    end_date: str = "2026-01-12T00:00:00",
    annual_growth_rate: float = 0.0,
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
            "annual_growth_rate": annual_growth_rate,
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


def test_hourly_weekday_and_trend_components_are_multiplied() -> None:
    config = traffic_config(annual_growth_rate=0.0)
    timestamp = datetime(2026, 1, 10, 12, tzinfo=ZoneInfo("America/New_York"))
    config.arrivals.hourly_intensity[12] = 0.5

    assert hourly_intensity(timestamp, config.arrivals) == 0.5
    assert weekday_intensity(timestamp, config.arrivals) == 0.45
    assert (
        trend_intensity(
            timestamp,
            config.dataset.start,
            config.dataset.end,
            config.arrivals,
        )
        == 1.0
    )
    assert (
        effective_intensity(
            timestamp,
            config.dataset.start,
            config.dataset.end,
            config.arrivals,
        )
        == 0.5 * 0.45 * 1.0
    )


def test_effective_arrival_rate_never_exceeds_maximum_rate() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2027-01-01T00:00:00",
        annual_growth_rate=0.2,
    )

    for timestamp in [
        config.dataset.start,
        datetime(2026, 6, 1, 12, tzinfo=config.dataset.timezone),
        config.dataset.end,
    ]:
        intensity = effective_intensity(
            timestamp,
            config.dataset.start,
            config.dataset.end,
            config.arrivals,
        )
        assert 0 <= intensity <= 1
        assert (
            arrival_rate_per_hour(
                timestamp,
                config.dataset.start,
                config.dataset.end,
                config.arrivals,
            )
            <= config.arrivals.maximum_rate_per_hour
        )


def test_midnight_remains_lower_than_noon_when_configured_that_way() -> None:
    config = traffic_config()
    config.arrivals.hourly_intensity[0] = 0.1
    config.arrivals.hourly_intensity[12] = 1.0
    midnight = datetime(2026, 1, 5, 0, tzinfo=config.dataset.timezone)
    noon = datetime(2026, 1, 5, 12, tzinfo=config.dataset.timezone)

    assert effective_intensity(
        midnight,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    ) < effective_intensity(
        noon,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )


def test_weekend_traffic_remains_lower_than_weekday_when_configured_that_way() -> None:
    config = traffic_config()
    monday = datetime(2026, 1, 5, 12, tzinfo=config.dataset.timezone)
    saturday = datetime(2026, 1, 10, 12, tzinfo=config.dataset.timezone)

    assert effective_intensity(
        monday,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    ) > effective_intensity(
        saturday,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )


def test_weekday_pattern_repeats_across_successive_weeks() -> None:
    config = traffic_config(end_date="2026-01-20T00:00:00")
    first_monday = datetime(2026, 1, 5, 12, tzinfo=config.dataset.timezone)
    second_monday = datetime(2026, 1, 12, 12, tzinfo=config.dataset.timezone)

    assert (
        weekday_intensity(first_monday, config.arrivals)
        == weekday_intensity(second_monday, config.arrivals)
        == 1.0
    )


def test_zero_growth_uses_constant_trend_intensity() -> None:
    config = traffic_config(annual_growth_rate=0.0)

    assert (
        trend_intensity(
            datetime(2026, 1, 8, 12, tzinfo=config.dataset.timezone),
            config.dataset.start,
            config.dataset.end,
            config.arrivals,
        )
        == 1.0
    )


def test_positive_growth_increases_and_is_normalized_to_one_at_end() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2027-01-01T00:00:00",
        annual_growth_rate=0.02,
    )

    start = trend_intensity(
        config.dataset.start,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )
    end = trend_intensity(
        config.dataset.end,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )

    assert start < end
    assert end == 1.0
    assert 0 <= start <= 1


def test_negative_growth_decreases_without_exceeding_one() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2027-01-01T00:00:00",
        annual_growth_rate=-0.03,
    )

    start = trend_intensity(
        config.dataset.start,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )
    end = trend_intensity(
        config.dataset.end,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )

    assert start == 1.0
    assert 0 <= end < start <= 1


def test_half_year_simulation_applies_half_the_annual_linear_effect() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2026-07-02T14:54:36",
        annual_growth_rate=-0.04,
    )

    end = trend_intensity(
        config.dataset.end,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )

    assert abs(end - 0.98) < 0.001


def test_multi_year_simulation_continues_linear_trend() -> None:
    config = traffic_config(
        start_date="2026-01-01T00:00:00",
        end_date="2028-01-01T11:39:36",
        annual_growth_rate=-0.05,
    )

    end = trend_intensity(
        config.dataset.end,
        config.dataset.start,
        config.dataset.end,
        config.arrivals,
    )

    assert abs(end - 0.90) < 0.001


def test_nhpp_generation_uses_combined_intensity() -> None:
    monday_config = traffic_config(
        start_date="2026-01-05T12:00:00",
        end_date="2026-01-05T13:00:00",
    )
    saturday_config = traffic_config(
        start_date="2026-01-10T12:00:00",
        end_date="2026-01-10T13:00:00",
    )
    monday_config.arrivals.hourly_intensity[12] = 1.0
    saturday_config.arrivals.hourly_intensity[12] = 1.0

    monday_arrivals = generate_arrivals(
        monday_config.dataset.start,
        monday_config.dataset.end,
        monday_config.arrivals,
        Random(42),  # noqa: S311
    )
    saturday_arrivals = generate_arrivals(
        saturday_config.dataset.start,
        saturday_config.dataset.end,
        saturday_config.arrivals,
        Random(42),  # noqa: S311
    )

    assert len(monday_arrivals) > len(saturday_arrivals)
