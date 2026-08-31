"""Synthetic website event-stream data models."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

EVENT_TYPE_PAGE_VIEW = "page_view"
EVENT_TYPE_CLICK = "click"
EVENT_TYPE_PRODUCT_VIEW = "product_view"
EVENT_TYPE_SEARCH = "search"
EVENT_TYPE_ADD_TO_CART = "add_to_cart"
EVENT_TYPE_BEGIN_CHECKOUT = "begin_checkout"
EVENT_TYPE_PURCHASE = "purchase"
EVENT_TYPE_FORM_SUBMIT = "form_submit"
EVENT_TYPE_NEWSLETTER_SIGNUP = "newsletter_signup"

SUPPORTED_EVENT_TYPES = frozenset(
    {
        EVENT_TYPE_PAGE_VIEW,
        EVENT_TYPE_CLICK,
        EVENT_TYPE_PRODUCT_VIEW,
        EVENT_TYPE_SEARCH,
        EVENT_TYPE_ADD_TO_CART,
        EVENT_TYPE_BEGIN_CHECKOUT,
        EVENT_TYPE_PURCHASE,
        EVENT_TYPE_FORM_SUBMIT,
        EVENT_TYPE_NEWSLETTER_SIGNUP,
    }
)


@dataclass
class Event:
    event_id: UUID
    visitor_id: UUID
    session_id: UUID
    page: str
    timestamp: datetime
    event_type: str = EVENT_TYPE_PAGE_VIEW
    properties: dict[str, object] = field(default_factory=dict)


@dataclass
class Session:
    visitor_id: UUID
    session_id: UUID
    session_start_time: datetime
    session_end_time: datetime | None = None
    campaign_id: str | None = None
    channel: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    events: list[Event] = field(default_factory=list)


@dataclass
class Visitor:
    visitor_id: UUID
    acquisition_source: str | None = None
    acquisition_campaign_id: str | None = None
    acquisition_utm_medium: str | None = None
    acquisition_utm_campaign: str | None = None
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
