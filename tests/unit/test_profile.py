from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from synthetic_website_data.config import (
    VisitorProfileConfig,
    VisitorProfileGeographyConfig,
    VisitorProfilePhaseConfig,
)
from synthetic_website_data.models import (
    EVENT_TYPE_NEWSLETTER_SIGNUP,
    EVENT_TYPE_PAGE_VIEW,
    EVENT_TYPE_PURCHASE,
    Event,
    Visitor,
)
from synthetic_website_data.profile import ProfileEnricher


def profile_config(  # noqa: PLR0913
    distribution_file: Path,
    *,
    enabled: bool = True,
    signup_enabled: bool = True,
    checkout_enabled: bool = True,
    signup_probability: float = 1.0,
    checkout_probability: float = 1.0,
    signup_fields: frozenset[str] = frozenset({"first_name", "last_name", "email"}),
    checkout_fields: frozenset[str] = frozenset(
        {
            "first_name",
            "last_name",
            "email",
            "phone",
            "shipping_state",
            "shipping_postal_code",
        }
    ),
) -> VisitorProfileConfig:
    return VisitorProfileConfig(
        enabled=enabled,
        signup=VisitorProfilePhaseConfig(
            enabled=signup_enabled,
            enrichment_probability=signup_probability,
            fields=signup_fields,
        ),
        checkout=VisitorProfilePhaseConfig(
            enabled=checkout_enabled,
            enrichment_probability=checkout_probability,
            fields=checkout_fields,
        ),
        geography=VisitorProfileGeographyConfig(
            enabled=True,
            distribution_file=distribution_file,
        ),
    )


@pytest.fixture
def geography_file(tmp_path: Path) -> Path:
    path = tmp_path / "us_geography.csv"
    path.write_text(
        "zip_code,state,area_code,population\n45202,OH,513,900\n10001,NY,212,100\n",
        encoding="utf-8",
    )
    return path


def test_new_visitor_starts_with_empty_profile() -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))

    assert visitor.profile.first_name is None
    assert visitor.profile.last_name is None
    assert visitor.profile.email is None
    assert visitor.profile.phone is None
    assert visitor.profile.shipping_state is None
    assert visitor.profile.shipping_postal_code is None


def test_signup_enriches_identity_only(geography_file: Path) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    event = event_with_type(EVENT_TYPE_NEWSLETTER_SIGNUP)
    enricher = ProfileEnricher(profile_config(geography_file), seed=42)

    enricher.enrich_event(visitor, event)

    assert visitor.profile.first_name
    assert visitor.profile.last_name
    assert visitor.profile.email
    assert visitor.profile.phone is None
    assert visitor.profile.shipping_state is None
    assert visitor.profile.shipping_postal_code is None
    assert set(event.properties) == {"first_name", "last_name", "email"}


def test_checkout_generates_missing_identity_contact_and_geography(
    geography_file: Path,
) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    event = event_with_type(EVENT_TYPE_PURCHASE, {"order_id": "ord_1"})
    enricher = ProfileEnricher(profile_config(geography_file), seed=42)

    enricher.enrich_event(visitor, event)

    assert visitor.profile.first_name
    assert visitor.profile.last_name
    assert visitor.profile.email
    assert visitor.profile.phone is not None
    assert visitor.profile.shipping_state == "OH"
    assert visitor.profile.shipping_postal_code == "45202"
    assert visitor.profile.phone.startswith("513-555-")
    assert event.properties["order_id"] == "ord_1"
    assert {
        "first_name",
        "last_name",
        "email",
        "phone",
        "shipping_state",
        "shipping_postal_code",
    }.issubset(event.properties)


def test_existing_signup_identity_is_reused_at_checkout(geography_file: Path) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    enricher = ProfileEnricher(profile_config(geography_file), seed=42)
    signup = event_with_type(EVENT_TYPE_NEWSLETTER_SIGNUP)
    purchase = event_with_type(EVENT_TYPE_PURCHASE)

    enricher.enrich_event(visitor, signup)
    identity = (
        visitor.profile.first_name,
        visitor.profile.last_name,
        visitor.profile.email,
    )
    enricher.enrich_event(visitor, purchase)

    assert (
        visitor.profile.first_name,
        visitor.profile.last_name,
        visitor.profile.email,
    ) == identity


def test_repeat_enrichment_does_not_regenerate_values(geography_file: Path) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    enricher = ProfileEnricher(profile_config(geography_file), seed=42)

    enricher.enrich_event(visitor, event_with_type(EVENT_TYPE_PURCHASE))
    first_profile = (
        visitor.profile.first_name,
        visitor.profile.last_name,
        visitor.profile.email,
        visitor.profile.phone,
        visitor.profile.shipping_state,
        visitor.profile.shipping_postal_code,
    )
    enricher.enrich_event(visitor, event_with_type(EVENT_TYPE_PURCHASE))

    assert (
        visitor.profile.first_name,
        visitor.profile.last_name,
        visitor.profile.email,
        visitor.profile.phone,
        visitor.profile.shipping_state,
        visitor.profile.shipping_postal_code,
    ) == first_profile


def test_anonymous_events_do_not_expose_profile_properties(
    geography_file: Path,
) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    event = event_with_type(EVENT_TYPE_PAGE_VIEW)
    enricher = ProfileEnricher(profile_config(geography_file), seed=42)

    enricher.enrich_event(visitor, event)

    assert event.properties == {}
    assert visitor.profile.email is None


def test_global_profile_toggle_disables_enrichment(geography_file: Path) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    event = event_with_type(EVENT_TYPE_PURCHASE)
    enricher = ProfileEnricher(
        profile_config(geography_file, enabled=False),
        seed=42,
    )

    enricher.enrich_event(visitor, event)

    assert event.properties == {}
    assert visitor.profile.email is None


def test_configured_field_subset_is_respected(geography_file: Path) -> None:
    visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    event = event_with_type(EVENT_TYPE_PURCHASE)
    enricher = ProfileEnricher(
        profile_config(
            geography_file,
            checkout_fields=frozenset({"shipping_state", "shipping_postal_code"}),
        ),
        seed=42,
    )

    enricher.enrich_event(visitor, event)

    assert event.properties == {
        "shipping_state": "OH",
        "shipping_postal_code": "45202",
    }
    assert visitor.profile.phone is None


def test_seeded_profile_generation_is_deterministic(geography_file: Path) -> None:
    first_visitor = Visitor(visitor_id=UUID("019a2222-2222-7222-8222-222222222222"))
    second_visitor = Visitor(visitor_id=UUID("019a3333-3333-7333-8333-333333333333"))
    first = ProfileEnricher(profile_config(geography_file), seed=42)
    second = ProfileEnricher(profile_config(geography_file), seed=42)

    first.enrich_event(first_visitor, event_with_type(EVENT_TYPE_PURCHASE))
    second.enrich_event(second_visitor, event_with_type(EVENT_TYPE_PURCHASE))

    assert first_visitor.profile == second_visitor.profile


def event_with_type(
    event_type: str,
    properties: dict[str, object] | None = None,
) -> Event:
    return Event(
        event_id=UUID("019a1111-1111-7111-8111-111111111111"),
        visitor_id=UUID("019a2222-2222-7222-8222-222222222222"),
        session_id=UUID("019a3333-3333-7333-8333-333333333333"),
        page="signup",
        timestamp=datetime(2026, 1, 1, 14, tzinfo=UTC),
        event_type=event_type,
        properties={} if properties is None else properties,
    )
