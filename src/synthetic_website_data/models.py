"""Synthetic website event-stream data models."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Event:
    event_id: UUID
    visitor_id: UUID
    session_id: UUID
    page: str
    timestamp: datetime


@dataclass
class Session:
    visitor_id: UUID
    session_id: UUID
    session_start_time: datetime
    session_end_time: datetime | None = None
    events: list[Event] = field(default_factory=list)


@dataclass
class Visitor:
    visitor_id: UUID
    sessions: list[Session] = field(default_factory=list)


@dataclass
class SyntheticDataset:
    visitors: list[Visitor] = field(default_factory=list)

    def iter_sessions(self) -> Iterator[Session]:
        """Yield sessions from the visitor hierarchy without flattening first."""
        for visitor in self.visitors:
            yield from visitor.sessions

    def iter_events(self) -> Iterator[Event]:
        """Yield events from the visitor hierarchy without flattening first."""
        for session in self.iter_sessions():
            yield from session.events

    @property
    def sessions(self) -> list[Session]:
        return list(self.iter_sessions())

    @property
    def events(self) -> list[Event]:
        return list(self.iter_events())


def session_converted(
    session: Session,
    conversion_pages: set[str] | frozenset[str],
) -> bool:
    """Return whether any page-view event reached a configured conversion page."""
    return any(event.page in conversion_pages for event in session.events)
