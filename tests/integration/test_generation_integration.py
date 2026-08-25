from random import Random

from synthetic_website_data.arrivals import generate_arrivals
from synthetic_website_data.config import parse_config
from synthetic_website_data.generators import generate_dataset
from synthetic_website_data.models import SyntheticDataset, session_converted
from synthetic_website_data.traversal import (
    delay_for_page,
    drop_off_probability_for_page,
)


def raw_generation_config(seed: int = 42) -> dict[str, object]:
    return {
        "dataset": {
            "start_date": "2026-01-01T09:00:00",
            "end_date": "2026-01-01T11:00:00",
            "timezone": "America/New_York",
            "random_seed": seed,
        },
        "website": {
            "entry_page": "home",
            "terminal_pages": ["checkout"],
            "graph": {
                "home": {"products": 1.0},
                "products": {"checkout": 1.0},
                "checkout": {},
            },
        },
        "arrivals": {
            "maximum_rate_per_hour": 200,
            "hourly_intensity": {hour: 1.0 if hour == 9 else 0.0 for hour in range(24)},
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


def test_same_seed_reproduces_same_output() -> None:
    first = generate_dataset(parse_config(raw_generation_config(seed=42)))
    second = generate_dataset(parse_config(raw_generation_config(seed=42)))

    assert fingerprint(first) == fingerprint(second)


def test_different_seeds_can_produce_different_output() -> None:
    first = generate_dataset(parse_config(raw_generation_config(seed=42)))
    second = generate_dataset(parse_config(raw_generation_config(seed=43)))

    assert fingerprint(first) != fingerprint(second)


def test_generated_dataset_has_required_hierarchy_and_ids() -> None:
    dataset = generate_dataset(parse_config(raw_generation_config()))

    assert dataset.visitors
    assert len(dataset.visitors) == len(dataset.sessions)
    assert len(dataset.events) >= len(dataset.sessions)
    assert dataset.sessions == [
        session for visitor in dataset.visitors for session in visitor.sessions
    ]
    assert dataset.events == [
        event for session in dataset.sessions for event in session.events
    ]

    visitor_ids = [visitor.visitor_id for visitor in dataset.visitors]
    session_ids = [session.session_id for session in dataset.sessions]
    event_ids = [event.event_id for event in dataset.events]
    assert len(visitor_ids) == len(set(visitor_ids))
    assert len(session_ids) == len(set(session_ids))
    assert len(event_ids) == len(set(event_ids))


def test_sessions_follow_graph_and_timestamp_rules() -> None:
    config = parse_config(raw_generation_config())
    dataset = generate_dataset(config)

    for session in dataset.sessions:
        assert session.events[0].page == config.website.entry_page
        assert session.session_start_time == session.events[0].timestamp
        assert session.session_end_time == session.events[-1].timestamp
        assert len(session.events) <= config.sessions.max_page_views

        for event in session.events:
            assert event.visitor_id == session.visitor_id
            assert event.session_id == session.session_id
            assert event.timestamp >= session.session_start_time
            assert event.timestamp < config.dataset.end

        for current, next_event in zip(
            session.events,
            session.events[1:],
            strict=False,
        ):
            assert next_event.timestamp > current.timestamp
            assert next_event.page in config.website.graph[current.page]

        if session.events[-1].page in config.website.terminal_pages:
            assert session.events[-1].page == "checkout"


def test_terminal_pages_terminate_session() -> None:
    dataset = generate_dataset(parse_config(raw_generation_config()))

    assert all(
        [event.page for event in session.events] == ["home", "products", "checkout"]
        for session in dataset.sessions
    )


def test_returning_visitor_rate_zero_produces_no_returning_visitors() -> None:
    raw = raw_generation_config()
    raw["visitors"] = {
        "returning_visitor_rate": 0.0,
        "max_sessions_per_visitor": 5,
    }
    config = parse_config(raw)
    dataset = generate_dataset(config)

    assert dataset.sessions
    assert all(len(visitor.sessions) == 1 for visitor in dataset.visitors)
    assert len(dataset.visitors) == len(dataset.sessions)


def test_returning_visitors_can_have_multiple_later_sessions() -> None:
    raw = raw_generation_config()
    raw["visitors"] = {
        "returning_visitor_rate": 1.0,
        "max_sessions_per_visitor": 5,
    }
    config = parse_config(raw)
    dataset = generate_dataset(config)
    arrivals = generate_arrivals(
        start=config.dataset.start,
        end=config.dataset.end,
        config=config.arrivals,
        rng=Random(config.dataset.random_seed),  # noqa: S311
    )

    session_counts = [len(visitor.sessions) for visitor in dataset.visitors]
    assert len(dataset.sessions) == len(arrivals)
    assert any(count > 1 for count in session_counts)
    assert any(count > 2 for count in session_counts)
    assert max(session_counts) <= config.visitors.max_sessions_per_visitor

    for visitor in dataset.visitors:
        for previous, current in zip(
            visitor.sessions,
            visitor.sessions[1:],
            strict=False,
        ):
            assert previous.session_end_time is not None
            assert current.session_start_time > previous.session_end_time


def test_returning_visitor_rate_targets_unique_returning_share() -> None:
    raw = raw_generation_config()
    dataset_config = raw["dataset"]
    assert isinstance(dataset_config, dict)
    dataset_config["end_date"] = "2026-01-02T09:00:00"
    arrivals_config = raw["arrivals"]
    assert isinstance(arrivals_config, dict)
    arrivals_config["maximum_rate_per_hour"] = 200
    arrivals_config["hourly_intensity"] = dict.fromkeys(range(24), 1.0)
    raw["visitors"] = {
        "returning_visitor_rate": 0.25,
        "max_sessions_per_visitor": 5,
    }
    config = parse_config(raw)
    dataset = generate_dataset(config)
    session_counts = [len(visitor.sessions) for visitor in dataset.visitors]

    observed_rate = sum(count > 1 for count in session_counts) / len(session_counts)

    assert abs(observed_rate - config.visitors.returning_visitor_rate) < 0.03


def test_returning_visitor_assignments_are_seeded() -> None:
    raw = raw_generation_config()
    raw["visitors"] = {
        "returning_visitor_rate": 0.75,
        "max_sessions_per_visitor": 4,
    }

    first = generate_dataset(parse_config(raw))
    second = generate_dataset(parse_config(raw))

    assert session_ownership_fingerprint(first) == session_ownership_fingerprint(second)


def test_page_drop_off_override_takes_precedence_over_global_default() -> None:
    raw = raw_generation_config()
    raw["sessions"] = {
        "default_drop_off_probability": 1.0,
        "max_page_views": 30,
    }
    website = raw["website"]
    assert isinstance(website, dict)
    website["pages"] = {"home": {"drop_off_probability": 0.0}}
    config = parse_config(raw)

    assert drop_off_probability_for_page(config.website, config.sessions, "home") == 0.0
    assert all(
        len(session.events) == 2 for session in generate_dataset(config).sessions
    )


def test_missing_page_drop_off_override_falls_back_to_global_default() -> None:
    raw = raw_generation_config()
    raw["sessions"] = {
        "default_drop_off_probability": 1.0,
        "max_page_views": 30,
    }
    config = parse_config(raw)

    assert drop_off_probability_for_page(config.website, config.sessions, "home") == 1.0
    assert all(
        len(session.events) == 1 for session in generate_dataset(config).sessions
    )


def test_page_gamma_delay_override_takes_precedence_over_global_default() -> None:
    raw = raw_generation_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["pages"] = {
        "products": {"delay": {"shape": 3.0, "scale_seconds": 10.0}},
    }
    config = parse_config(raw)

    delay = delay_for_page(config.website, config.page_views, "products")

    assert delay.shape == 3.0
    assert delay.scale_seconds == 10.0


def test_missing_page_gamma_delay_override_falls_back_to_global_default() -> None:
    config = parse_config(raw_generation_config())

    delay = delay_for_page(config.website, config.page_views, "home")

    assert delay == config.page_views.default_delay


def test_conversion_is_derived_from_configured_event_pages() -> None:
    raw = raw_generation_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["terminal_pages"] = ["order_confirmation"]
    website["conversion_pages"] = ["order_confirmation"]
    website["graph"] = {
        "home": {"checkout": 1.0},
        "checkout": {"order_confirmation": 1.0},
        "order_confirmation": {},
    }
    config = parse_config(raw)
    dataset = generate_dataset(config)

    assert all(
        session_converted(session, config.website.conversion_pages)
        for session in dataset.sessions
    )
    assert all(
        [event.page for event in session.events]
        == ["home", "checkout", "order_confirmation"]
        for session in dataset.sessions
    )


def test_checkout_without_order_confirmation_is_not_a_conversion() -> None:
    raw = raw_generation_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["conversion_pages"] = ["order_confirmation"]
    website["terminal_pages"] = ["checkout", "order_confirmation"]
    website["graph"] = {
        "home": {"checkout": 1.0},
        "checkout": {},
        "order_confirmation": {},
    }
    config = parse_config(raw)
    dataset = generate_dataset(config)

    assert not any(
        session_converted(session, config.website.conversion_pages)
        for session in dataset.sessions
    )


def test_multiple_conversion_pages_are_supported() -> None:
    raw = raw_generation_config()
    website = raw["website"]
    assert isinstance(website, dict)
    website["conversion_pages"] = ["products", "checkout"]
    config = parse_config(raw)
    dataset = generate_dataset(config)

    assert all(
        session_converted(session, config.website.conversion_pages)
        for session in dataset.sessions
    )


def test_max_page_views_prevents_infinite_cycles() -> None:
    raw = raw_generation_config()
    raw["website"] = {
        "entry_page": "home",
        "terminal_pages": [],
        "graph": {
            "home": {"home": 1.0},
        },
    }
    raw["sessions"] = {
        "drop_off_probability": 0.0,
        "max_page_views": 5,
    }
    dataset = generate_dataset(parse_config(raw))

    assert dataset.sessions
    assert all(len(session.events) == 5 for session in dataset.sessions)


def test_iterators_traverse_hierarchy_without_returning_lists() -> None:
    dataset = generate_dataset(parse_config(raw_generation_config()))

    sessions_iterator = dataset.iter_sessions()
    events_iterator = dataset.iter_events()

    assert not isinstance(sessions_iterator, list)
    assert not isinstance(events_iterator, list)
    assert list(dataset.iter_sessions()) == dataset.sessions
    assert list(dataset.iter_events()) == dataset.events


def fingerprint(dataset: SyntheticDataset) -> list[tuple[str, str, str, str, str]]:
    return [
        (
            str(event.visitor_id),
            str(event.session_id),
            str(event.event_id),
            event.page,
            event.timestamp.isoformat(),
        )
        for event in dataset.events
    ]


def session_ownership_fingerprint(dataset: SyntheticDataset) -> list[tuple[str, str]]:
    return [
        (str(session.visitor_id), str(session.session_id))
        for session in dataset.iter_sessions()
    ]
