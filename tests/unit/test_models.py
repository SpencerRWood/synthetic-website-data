from datetime import UTC, datetime
from uuid import UUID

from synthetic_website_data.models import (
    EVENT_TYPE_ADD_TO_CART,
    EVENT_TYPE_PAGE_VIEW,
    Event,
)


def test_event_can_be_created_with_event_type_and_arbitrary_properties() -> None:
    event = Event(
        event_id=UUID("019a1111-1111-7111-8111-111111111111"),
        visitor_id=UUID("019a2222-2222-7222-8222-222222222222"),
        session_id=UUID("019a3333-3333-7333-8333-333333333333"),
        page="/products/123",
        timestamp=datetime(2026, 1, 1, 14, tzinfo=UTC),
        event_type=EVENT_TYPE_ADD_TO_CART,
        properties={
            "product_id": "123",
            "quantity": 2,
            "price": 89.99,
        },
    )

    assert event.event_type == EVENT_TYPE_ADD_TO_CART
    assert event.properties == {
        "product_id": "123",
        "quantity": 2,
        "price": 89.99,
    }


def test_event_defaults_to_page_view_with_empty_properties() -> None:
    event = Event(
        event_id=UUID("019a1111-1111-7111-8111-111111111111"),
        visitor_id=UUID("019a2222-2222-7222-8222-222222222222"),
        session_id=UUID("019a3333-3333-7333-8333-333333333333"),
        page="/",
        timestamp=datetime(2026, 1, 1, 14, tzinfo=UTC),
    )

    assert event.event_type == EVENT_TYPE_PAGE_VIEW
    assert event.properties == {}


def test_different_event_types_can_use_different_property_keys() -> None:
    product_event = Event(
        event_id=UUID("019a1111-1111-7111-8111-111111111111"),
        visitor_id=UUID("019a2222-2222-7222-8222-222222222222"),
        session_id=UUID("019a3333-3333-7333-8333-333333333333"),
        page="/products/123",
        timestamp=datetime(2026, 1, 1, 14, tzinfo=UTC),
        event_type="product_view",
        properties={"product_id": "123", "price": 89.99},
    )
    search_event = Event(
        event_id=UUID("019a4444-4444-7444-8444-444444444444"),
        visitor_id=product_event.visitor_id,
        session_id=product_event.session_id,
        page="/search",
        timestamp=datetime(2026, 1, 1, 14, 1, tzinfo=UTC),
        event_type="search",
        properties={"search_query": "running shoes", "results_count": 42},
    )

    assert set(product_event.properties) == {"product_id", "price"}
    assert set(search_event.properties) == {"search_query", "results_count"}
