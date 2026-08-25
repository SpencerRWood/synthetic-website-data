"""Synthetic website event-stream generation."""

from datetime import datetime
from random import Random
from uuid import UUID

from .arrivals import generate_arrivals
from .config import GeneratorConfig
from .models import Event, Session, SyntheticDataset, Visitor
from .traversal import traverse_session_pages


def generate_visitor(rng: Random) -> Visitor:
    return Visitor(visitor_id=_deterministic_uuid(rng))


def generate_session(
    visitor: Visitor,
    session_start_time: datetime,
    rng: Random,
) -> Session:
    session = Session(
        visitor_id=visitor.visitor_id,
        session_id=_deterministic_uuid(rng),
        session_start_time=session_start_time,
    )
    visitor.sessions.append(session)
    return session


def generate_event(
    visitor: Visitor,
    session: Session,
    page: str,
    timestamp: datetime,
    rng: Random,
) -> Event:
    event = Event(
        event_id=_deterministic_uuid(rng),
        visitor_id=visitor.visitor_id,
        session_id=session.session_id,
        page=page,
        timestamp=timestamp,
    )

    session.events.append(event)
    return event


def generate_dataset(config: GeneratorConfig) -> SyntheticDataset:
    """Generate a hierarchical synthetic website event-stream dataset."""
    rng = Random(config.dataset.random_seed)  # noqa: S311
    dataset = SyntheticDataset()
    pending_return_visitors: list[Visitor] = []
    arrivals = generate_arrivals(
        start=config.dataset.start,
        end=config.dataset.end,
        config=config.arrivals,
        rng=rng,
    )

    for arrival in arrivals:
        visitor = _assign_visitor(
            dataset=dataset,
            pending_return_visitors=pending_return_visitors,
            arrival=arrival,
            config=config,
            rng=rng,
        )
        session = generate_session(visitor, arrival, rng)
        for page, timestamp in traverse_session_pages(
            website=config.website,
            page_view_config=config.page_views,
            sessions=config.sessions,
            max_page_views=config.sessions.max_page_views,
            start_time=arrival,
            end_time=config.dataset.end,
            rng=rng,
        ):
            generate_event(visitor, session, page, timestamp, rng)
        session.session_end_time = session.events[-1].timestamp

    return dataset


def _assign_visitor(
    *,
    dataset: SyntheticDataset,
    pending_return_visitors: list[Visitor],
    arrival: datetime,
    config: GeneratorConfig,
    rng: Random,
) -> Visitor:
    if (
        config.visitors.returning_visitor_rate == 0
        or config.visitors.max_sessions_per_visitor == 1
    ):
        return _create_visitor(dataset, rng)

    eligible_pending_visitors = [
        visitor
        for visitor in pending_return_visitors
        if _visitor_can_receive_session(visitor, arrival, config)
    ]
    if eligible_pending_visitors:
        visitor = rng.choice(eligible_pending_visitors)
        pending_return_visitors.remove(visitor)
        return visitor

    eligible_returning_visitors = [
        visitor
        for visitor in dataset.visitors
        if len(visitor.sessions) > 1
        and _visitor_can_receive_session(visitor, arrival, config)
    ]
    if (
        eligible_returning_visitors
        and rng.random() < config.visitors.returning_visitor_rate
    ):
        return rng.choice(eligible_returning_visitors)

    visitor = _create_visitor(dataset, rng)
    if rng.random() < config.visitors.returning_visitor_rate:
        pending_return_visitors.append(visitor)
    return visitor


def _create_visitor(dataset: SyntheticDataset, rng: Random) -> Visitor:
    visitor = generate_visitor(rng)
    dataset.visitors.append(visitor)
    return visitor


def _visitor_can_receive_session(
    visitor: Visitor,
    arrival: datetime,
    config: GeneratorConfig,
) -> bool:
    if len(visitor.sessions) >= config.visitors.max_sessions_per_visitor:
        return False
    previous_session = visitor.sessions[-1]
    previous_time = previous_session.session_end_time
    if previous_time is None:
        previous_time = previous_session.session_start_time
    return arrival > previous_time


def _deterministic_uuid(rng: Random) -> UUID:
    return UUID(int=rng.getrandbits(128), version=4)
