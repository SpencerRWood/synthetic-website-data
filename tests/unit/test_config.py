from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from synthetic_website_data.config import ConfigurationError, load_config, parse_config


def valid_raw_config() -> dict[str, object]:
    return {
        "dataset": {
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "timezone": "America/New_York",
            "random_seed": 42,
        },
        "website": {
            "entry_page": "home",
            "terminal_pages": ["checkout"],
            "graph": {
                "home": {"products": 0.5, "blog": 0.5},
                "products": {"checkout": 1.0},
                "blog": {"home": 1.0},
                "checkout": {},
            },
        },
        "arrivals": {
            "maximum_rate_per_hour": 10,
            "hourly_intensity": dict.fromkeys(range(24), 0.5),
        },
        "sessions": {
            "drop_off_probability": 0.3,
            "max_page_views": 30,
        },
        "page_views": {
            "delay": {
                "distribution": "gamma",
                "shape": 2.0,
                "scale_seconds": 5.0,
            },
        },
    }


def test_valid_configuration_loads(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
dataset:
  start_date: "2026-01-01"
  end_date: "2026-01-02"
  timezone: "America/New_York"
  random_seed: 42
website:
  entry_page: home
  terminal_pages:
    - checkout
  graph:
    home:
      products: 0.5
      checkout: 0.5
    products:
      checkout: 1.0
    checkout: {}
arrivals:
  maximum_rate_per_hour: 10
  hourly_intensity:
    0: 0.1
    1: 0.1
    2: 0.1
    3: 0.1
    4: 0.1
    5: 0.1
    6: 0.1
    7: 0.1
    8: 0.1
    9: 0.1
    10: 0.1
    11: 0.1
    12: 0.1
    13: 0.1
    14: 0.1
    15: 0.1
    16: 0.1
    17: 0.1
    18: 0.1
    19: 0.1
    20: 0.1
    21: 0.1
    22: 0.1
    23: 0.1
sessions:
  drop_off_probability: 0.3
  max_page_views: 30
page_views:
  delay:
    distribution: gamma
    shape: 2.0
    scale_seconds: 5.0
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.website.entry_page == "home"
    assert config.dataset.start.isoformat() == "2026-01-01T00:00:00-05:00"


def test_new_behavior_configuration_loads() -> None:
    raw = valid_raw_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["conversion_pages"] = ["checkout"]
    website["pages"] = {
        "home": {"drop_off_probability": 0.25},
        "products": {
            "drop_off_probability": 0.10,
            "delay": {"shape": 2.5, "scale_seconds": 7.0},
        },
    }
    sessions = raw["sessions"]
    assert isinstance(sessions, dict)
    sessions["default_drop_off_probability"] = sessions.pop("drop_off_probability")
    page_views = raw["page_views"]
    assert isinstance(page_views, dict)
    page_views["default_delay"] = page_views.pop("delay")
    raw["visitors"] = {
        "returning_visitor_rate": 0.25,
        "max_sessions_per_visitor": 5,
    }

    config = parse_config(raw)

    assert config.visitors.returning_visitor_rate == 0.25
    assert config.visitors.max_sessions_per_visitor == 5
    assert config.website.conversion_pages == frozenset({"checkout"})
    assert config.website.pages["products"].delay is not None
    assert config.sessions.default_drop_off_probability == 0.3
    assert config.page_views.default_delay.shape == 2.0


def test_invalid_transition_probabilities_are_rejected() -> None:
    raw = valid_raw_config()
    home = _graph(raw)["home"]
    home["products"] = 1.2

    with pytest.raises(ConfigurationError, match="between 0 and 1"):
        parse_config(raw)


def test_outgoing_transition_weights_must_sum_to_one() -> None:
    raw = valid_raw_config()
    home = _graph(raw)["home"]
    home["products"] = 0.4

    with pytest.raises(ConfigurationError, match=r"must sum to 1\.0"):
        parse_config(raw)


def test_missing_graph_destinations_are_rejected() -> None:
    raw = valid_raw_config()
    home = _graph(raw)["home"]
    home["missing"] = home.pop("blog")

    with pytest.raises(ConfigurationError, match="missing destination"):
        parse_config(raw)


def test_terminal_nodes_cannot_have_outgoing_edges() -> None:
    raw = valid_raw_config()
    _graph(raw)["checkout"] = {"home": 1.0}

    with pytest.raises(ConfigurationError, match="terminal pages"):
        parse_config(raw)


def test_empty_nodes_must_be_explicit_terminal_pages() -> None:
    raw = valid_raw_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["terminal_pages"] = []

    with pytest.raises(ConfigurationError, match="non-terminal pages"):
        parse_config(raw)


@pytest.mark.parametrize(("hour", "intensity"), [(3, 1.1), (4, -0.1)])
def test_hourly_arrival_intensity_bounds(hour: int, intensity: float) -> None:
    raw = valid_raw_config()
    _hourly_intensity(raw)[hour] = intensity

    with pytest.raises(ConfigurationError, match="between 0 and 1"):
        parse_config(raw)


def test_all_24_hourly_intensity_values_are_required() -> None:
    raw = valid_raw_config()
    del _hourly_intensity(raw)[23]

    with pytest.raises(ConfigurationError, match="hours 0-23"):
        parse_config(raw)


@pytest.mark.parametrize("rate", [-0.1, 1.1])
def test_invalid_returning_visitor_rate_is_rejected(rate: float) -> None:
    raw = valid_raw_config()
    raw["visitors"] = {
        "returning_visitor_rate": rate,
        "max_sessions_per_visitor": 5,
    }

    with pytest.raises(ConfigurationError, match="returning_visitor_rate"):
        parse_config(raw)


def test_invalid_max_sessions_per_visitor_is_rejected() -> None:
    raw = valid_raw_config()
    raw["visitors"] = {
        "returning_visitor_rate": 0.25,
        "max_sessions_per_visitor": 0,
    }

    with pytest.raises(ConfigurationError, match="max_sessions_per_visitor"):
        parse_config(raw)


def test_invalid_default_drop_off_probability_is_rejected() -> None:
    raw = valid_raw_config()
    sessions = raw["sessions"]
    assert isinstance(sessions, dict)
    sessions["default_drop_off_probability"] = 1.1
    sessions.pop("drop_off_probability")

    with pytest.raises(ConfigurationError, match="default_drop_off_probability"):
        parse_config(raw)


def test_invalid_page_drop_off_probability_is_rejected() -> None:
    raw = valid_raw_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["pages"] = {"home": {"drop_off_probability": -0.1}}

    with pytest.raises(ConfigurationError, match=r"pages\.\*\.drop_off_probability"):
        parse_config(raw)


@pytest.mark.parametrize(
    "delay",
    [
        {"shape": 0.0, "scale_seconds": 5.0},
        {"shape": 2.0, "scale_seconds": 0.0},
    ],
)
def test_invalid_page_gamma_parameters_are_rejected(
    delay: dict[str, float],
) -> None:
    raw = valid_raw_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["pages"] = {"home": {"delay": delay}}

    with pytest.raises(ConfigurationError, match=r"website\.pages\.\*\.delay"):
        parse_config(raw)


def test_invalid_page_override_name_is_rejected() -> None:
    raw = valid_raw_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["pages"] = {"missing": {"drop_off_probability": 0.1}}

    with pytest.raises(ConfigurationError, match=r"website\.pages overrides"):
        parse_config(raw)


def test_invalid_conversion_page_name_is_rejected() -> None:
    raw = valid_raw_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["conversion_pages"] = ["missing"]

    with pytest.raises(ConfigurationError, match="conversion page"):
        parse_config(raw)


@pytest.mark.parametrize(
    "delay",
    [
        {"distribution": "normal", "shape": 2.0, "scale_seconds": 5.0},
        {"distribution": "gamma", "shape": -1.0, "scale_seconds": 5.0},
        {"distribution": "gamma", "shape": 2.0, "scale_seconds": -1.0},
    ],
)
def test_invalid_default_gamma_parameters_are_rejected(
    delay: dict[str, float | str],
) -> None:
    raw = valid_raw_config()
    page_views = raw["page_views"]
    assert isinstance(page_views, dict)
    page_views["default_delay"] = delay
    page_views.pop("delay")

    with pytest.raises(ConfigurationError, match=r"page_views\.default_delay"):
        parse_config(raw)


def test_valid_raw_config_fixture_is_independent() -> None:
    first = valid_raw_config()
    second = deepcopy(first)

    assert parse_config(first) == parse_config(second)


def _graph(raw: dict[str, object]) -> dict[str, dict[str, float]]:
    website = raw["website"]
    assert isinstance(website, dict)
    graph = website["graph"]
    assert isinstance(graph, dict)
    return cast("dict[str, dict[str, float]]", graph)


def _hourly_intensity(raw: dict[str, object]) -> dict[int, float]:
    arrivals = raw["arrivals"]
    assert isinstance(arrivals, dict)
    hourly = arrivals["hourly_intensity"]
    assert isinstance(hourly, dict)
    return cast("dict[int, float]", hourly)
