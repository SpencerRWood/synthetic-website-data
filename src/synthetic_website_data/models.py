"""Synthetic website event-stream data models."""

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

    @property
    def sessions(self) -> list[Session]:
        return [session for visitor in self.visitors for session in visitor.sessions]

    @property
    def events(self) -> list[Event]:
        return [event for session in self.sessions for event in session.events]
