"""Synthetic website event-stream generation."""

from datetime import datetime
from random import Random
from uuid import UUID

from .arrivals import generate_arrivals
from .config import (
    EventPropertiesConfig,
    EventPropertySpec,
    GeneratorConfig,
    WebsiteConfig,
)
from .models import (
    EVENT_TYPE_ADD_TO_CART,
    EVENT_TYPE_BEGIN_CHECKOUT,
    EVENT_TYPE_FORM_SUBMIT,
    EVENT_TYPE_NEWSLETTER_SIGNUP,
    EVENT_TYPE_PAGE_VIEW,
    EVENT_TYPE_PRODUCT_VIEW,
    EVENT_TYPE_PURCHASE,
    EVENT_TYPE_SEARCH,
    Event,
    Session,
    SyntheticDataset,
    Visitor,
)
from .profile import ProfileEnricher
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


def generate_event(  # noqa: PLR0913
    session: Session,
    page: str,
    timestamp: datetime,
    rng: Random,
    *,
    config: GeneratorConfig | None = None,
    visitor: Visitor | None = None,
    profile_enricher: ProfileEnricher | None = None,
) -> Event:
    event_id = _deterministic_uuid(rng)
    event_type = event_type_for_page(page, config.website if config else None)
    property_rng = Random(event_id.int)  # noqa: S311
    event = Event(
        event_id=event_id,
        visitor_id=session.visitor_id,
        session_id=session.session_id,
        page=page,
        timestamp=timestamp,
        event_type=event_type,
        properties=properties_for_event(
            event_type,
            page,
            property_rng,
            config.event_properties if config else None,
        ),
    )

    session.events.append(event)
    if visitor is not None and profile_enricher is not None:
        profile_enricher.enrich_event(visitor, event)
    return event


def event_type_for_page(page: str, website: WebsiteConfig | None = None) -> str:
    """Return the generated event type associated with a visited page."""
    page_config = website.pages.get(page) if website is not None else None
    if page_config is not None and page_config.event_type is not None:
        return page_config.event_type

    normalized = _normalize_page_name(page)
    event_type = EVENT_TYPE_PAGE_VIEW
    if "product" in normalized:
        event_type = EVENT_TYPE_PRODUCT_VIEW
    elif "search" in normalized:
        event_type = EVENT_TYPE_SEARCH
    elif normalized in {"cart", "add_to_cart"}:
        event_type = EVENT_TYPE_ADD_TO_CART
    elif "checkout" in normalized:
        event_type = EVENT_TYPE_BEGIN_CHECKOUT
    elif normalized in {"purchase", "confirmation", "order_confirmation", "thank_you"}:
        event_type = EVENT_TYPE_PURCHASE
    elif "newsletter" in normalized or "signup" in normalized:
        event_type = EVENT_TYPE_NEWSLETTER_SIGNUP
    elif "form" in normalized or "contact" in normalized:
        event_type = EVENT_TYPE_FORM_SUBMIT
    return event_type


def properties_for_event(
    event_type: str,
    page: str,
    rng: Random,
    event_properties: EventPropertiesConfig | None = None,
) -> dict[str, object]:
    """Return generic synthetic properties for the generated event."""
    if event_properties is not None:
        specs = event_properties.event_types.get(event_type)
        if specs is not None:
            return {
                property_name: _generate_configured_property(spec, rng)
                for property_name, spec in specs.items()
            }

    properties: dict[str, object] = {}
    if event_type == EVENT_TYPE_PRODUCT_VIEW:
        product_id, category, price = _synthetic_product(rng)
        properties = {
            "product_id": product_id,
            "category": category,
            "price": price,
        }
    elif event_type == EVENT_TYPE_ADD_TO_CART:
        product_id, _category, price = _synthetic_product(rng)
        quantity = rng.randint(1, 4)
        properties = {
            "product_id": product_id,
            "quantity": quantity,
            "price": price,
            "cart_value": _money(price * quantity),
        }
    elif event_type == EVENT_TYPE_SEARCH:
        query = rng.choice(SEARCH_QUERIES)
        properties = {
            "search_query": query,
            "results_count": rng.randint(0, 120),
        }
    elif event_type == EVENT_TYPE_BEGIN_CHECKOUT:
        properties = {
            "items_count": rng.randint(1, 6),
            "cart_value": _money(rng.uniform(24.0, 450.0)),
        }
    elif event_type == EVENT_TYPE_PURCHASE:
        properties = {
            "order_id": f"ord_{rng.randrange(1_000_000, 10_000_000)}",
            "items_count": rng.randint(1, 6),
            "order_value": _money(rng.uniform(24.0, 450.0)),
        }
    elif event_type == EVENT_TYPE_FORM_SUBMIT:
        properties = {"form_id": _form_id_for_page(page)}
    elif event_type == EVENT_TYPE_NEWSLETTER_SIGNUP:
        properties = {"newsletter_id": "default"}
    return properties


def generate_dataset(config: GeneratorConfig) -> SyntheticDataset:
    """Generate a hierarchical synthetic website event-stream dataset."""
    rng = Random(config.dataset.random_seed)  # noqa: S311
    profile_enricher = ProfileEnricher(
        config.visitor_profile,
        config.dataset.random_seed,
    )
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
            generate_event(
                session,
                page,
                timestamp,
                rng,
                config=config,
                visitor=visitor,
                profile_enricher=profile_enricher,
            )
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


def _normalize_page_name(page: str) -> str:
    return page.strip("/").replace("-", "_").replace("/", "_")


PRODUCT_CATEGORIES = (
    "apparel",
    "accessories",
    "footwear",
    "home",
    "outdoor",
)

SEARCH_QUERIES = (
    "running shoes",
    "linen shirt",
    "travel backpack",
    "desk lamp",
    "water bottle",
    "wireless headphones",
)


def _synthetic_product(rng: Random) -> tuple[str, str, float]:
    return (
        f"sku_{rng.randrange(1000, 10000)}",
        rng.choice(PRODUCT_CATEGORIES),
        _money(rng.uniform(12.0, 240.0)),
    )


def _money(value: float) -> float:
    return round(value, 2)


def _form_id_for_page(page: str) -> str:
    normalized = _normalize_page_name(page)
    return f"{normalized or 'page'}_form"


def _generate_configured_property(
    spec: EventPropertySpec,
    rng: Random,
) -> object:
    if spec.kind == "choice":
        return rng.choice(spec.values)
    if spec.kind == "float":
        return round(
            rng.uniform(_required_number(spec.minimum), _required_number(spec.maximum)),
            spec.decimals,
        )
    if spec.kind == "id":
        minimum = int(_required_number(spec.minimum))
        maximum = int(_required_number(spec.maximum))
        return f"{spec.prefix}{rng.randint(minimum, maximum)}"
    if spec.kind == "integer":
        return rng.randint(
            int(_required_number(spec.minimum)),
            int(_required_number(spec.maximum)),
        )
    return spec.value


def _required_number(value: float | None) -> float:
    if value is None:
        raise ValueError("configured numeric property is missing a bound")
    return value
