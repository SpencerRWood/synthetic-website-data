"""Synthetic website event-stream generation."""

from datetime import datetime
from random import Random
from uuid import UUID

from .arrivals import Arrival, generate_arrival_records
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
from .traversal import traverse_session_pages


def generate_visitor(
    rng: Random,
    *,
    acquisition_source: str | None = None,
    acquisition_campaign_id: str | None = None,
    acquisition_utm_medium: str | None = None,
    acquisition_utm_campaign: str | None = None,
) -> Visitor:
    return Visitor(
        visitor_id=_deterministic_uuid(rng),
        acquisition_source=acquisition_source,
        acquisition_campaign_id=acquisition_campaign_id,
        acquisition_utm_medium=acquisition_utm_medium,
        acquisition_utm_campaign=acquisition_utm_campaign,
    )


def generate_session(
    visitor: Visitor,
    session_start_time: datetime,
    rng: Random,
    *,
    campaign_source: Arrival | None = None,
) -> Session:
    session = Session(
        visitor_id=visitor.visitor_id,
        session_id=_deterministic_uuid(rng),
        session_start_time=session_start_time,
        campaign_id=campaign_source.campaign_id if campaign_source else None,
        channel=campaign_source.channel if campaign_source else None,
        utm_source=campaign_source.utm_source if campaign_source else None,
        utm_medium=campaign_source.utm_medium if campaign_source else None,
        utm_campaign=campaign_source.utm_campaign if campaign_source else None,
    )
    visitor.sessions.append(session)
    return session


def generate_event(
    session: Session,
    page: str,
    timestamp: datetime,
    rng: Random,
    *,
    config: GeneratorConfig | None = None,
) -> Event:
    event_id = _deterministic_uuid(rng)
    event_type = event_type_for_page(page, config.website if config else None)
    property_rng = Random(event_id.int)  # noqa: S311
    properties = properties_for_event(
        event_type,
        page,
        property_rng,
        config.event_properties if config else None,
    )
    if event_type == EVENT_TYPE_PAGE_VIEW:
        properties.update(_campaign_properties_for_session(session))

    event = Event(
        event_id=event_id,
        visitor_id=session.visitor_id,
        session_id=session.session_id,
        page=page,
        timestamp=timestamp,
        event_type=event_type,
        properties=properties,
    )

    session.events.append(event)
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
    dataset = SyntheticDataset()
    pending_return_visitors: list[Visitor] = []
    arrivals = generate_arrival_records(
        start=config.dataset.start,
        end=config.dataset.end,
        config=config.arrivals,
        rng=rng,
        campaigns=config.campaigns,
    )

    for arrival in arrivals:
        visitor = _assign_visitor(
            dataset=dataset,
            pending_return_visitors=pending_return_visitors,
            arrival=arrival,
            config=config,
            rng=rng,
        )
        session = generate_session(
            visitor,
            arrival.timestamp,
            rng,
            campaign_source=arrival,
        )
        for page, timestamp in traverse_session_pages(
            website=config.website,
            page_view_config=config.page_views,
            sessions=config.sessions,
            max_page_views=config.sessions.max_page_views,
            start_time=arrival.timestamp,
            end_time=config.dataset.end,
            rng=rng,
        ):
            generate_event(
                session,
                page,
                timestamp,
                rng,
                config=config,
            )
        session.session_end_time = session.events[-1].timestamp

    return dataset


def _assign_visitor(
    *,
    dataset: SyntheticDataset,
    pending_return_visitors: list[Visitor],
    arrival: Arrival,
    config: GeneratorConfig,
    rng: Random,
) -> Visitor:
    if (
        config.visitors.returning_visitor_rate == 0
        or config.visitors.max_sessions_per_visitor == 1
    ):
        return _create_visitor(dataset, rng, arrival=arrival)

    eligible_pending_visitors = [
        visitor
        for visitor in pending_return_visitors
        if _visitor_can_receive_session(visitor, arrival.timestamp, config)
    ]
    if eligible_pending_visitors:
        visitor = rng.choice(eligible_pending_visitors)
        pending_return_visitors.remove(visitor)
        return visitor

    eligible_returning_visitors = [
        visitor
        for visitor in dataset.visitors
        if len(visitor.sessions) > 1
        and _visitor_can_receive_session(visitor, arrival.timestamp, config)
    ]
    if (
        eligible_returning_visitors
        and rng.random() < config.visitors.returning_visitor_rate
    ):
        return rng.choice(eligible_returning_visitors)

    visitor = _create_visitor(dataset, rng, arrival=arrival)
    if rng.random() < config.visitors.returning_visitor_rate:
        pending_return_visitors.append(visitor)
    return visitor


def _create_visitor(
    dataset: SyntheticDataset,
    rng: Random,
    *,
    arrival: Arrival | None = None,
) -> Visitor:
    visitor = generate_visitor(
        rng,
        acquisition_source=arrival.channel if arrival is not None else None,
        acquisition_campaign_id=arrival.campaign_id if arrival is not None else None,
        acquisition_utm_medium=arrival.utm_medium if arrival is not None else None,
        acquisition_utm_campaign=arrival.utm_campaign if arrival is not None else None,
    )
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


def _campaign_properties_for_session(session: Session) -> dict[str, object]:
    properties: dict[str, object] = {}
    if session.utm_source is not None:
        properties["utm_source"] = session.utm_source
    if session.utm_medium is not None:
        properties["utm_medium"] = session.utm_medium
    if session.utm_campaign is not None:
        properties["utm_campaign"] = session.utm_campaign
    if session.campaign_id is not None:
        properties["campaign_id"] = session.campaign_id
    if session.channel is not None:
        properties["channel"] = session.channel
    return properties


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
