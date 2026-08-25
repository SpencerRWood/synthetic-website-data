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
    arrivals = generate_arrivals(
        start=config.dataset.start,
        end=config.dataset.end,
        config=config.arrivals,
        rng=rng,
    )

    for arrival in arrivals:
        visitor = generate_visitor(rng)
        session = generate_session(visitor, arrival, rng)
        for page, timestamp in traverse_session_pages(
            website=config.website,
            delay=config.page_views.delay,
            drop_off_probability=config.sessions.drop_off_probability,
            max_page_views=config.sessions.max_page_views,
            start_time=arrival,
            end_time=config.dataset.end,
            rng=rng,
        ):
            generate_event(visitor, session, page, timestamp, rng)
        session.session_end_time = session.events[-1].timestamp
        dataset.visitors.append(visitor)

    return dataset


def _deterministic_uuid(rng: Random) -> UUID:
    return UUID(int=rng.getrandbits(128), version=4)
