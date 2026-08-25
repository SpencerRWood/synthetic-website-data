from synthetic_website_data.config import parse_config
from synthetic_website_data.generators import generate_dataset
from synthetic_website_data.models import SyntheticDataset


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
