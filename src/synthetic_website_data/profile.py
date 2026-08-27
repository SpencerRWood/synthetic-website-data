"""Lifecycle-based visitor profile enrichment."""

from random import Random

from faker import Faker

from .config import (
    VisitorProfileConfig,
    VisitorProfilePhaseConfig,
)
from .distributions import GeographyDistribution, load_geography_distribution
from .models import (
    EVENT_TYPE_NEWSLETTER_SIGNUP,
    EVENT_TYPE_PURCHASE,
    Event,
    Visitor,
    VisitorProfile,
)

SIGNUP_EVENT_TYPES = frozenset({EVENT_TYPE_NEWSLETTER_SIGNUP})
CHECKOUT_EVENT_TYPES = frozenset({EVENT_TYPE_PURCHASE})


class ProfileEnricher:
    """Generate and persist profile fields when lifecycle events observe them."""

    def __init__(self, config: VisitorProfileConfig, seed: int | None) -> None:
        self.config = config
        self.rng = Random(seed)  # noqa: S311
        self.fake = Faker("en_US")
        if seed is not None:
            self.fake.seed_instance(seed)
        self.geography = self._load_geography(config)

    def enrich_event(self, visitor: Visitor, event: Event) -> None:
        if not self.config.enabled:
            return

        if event.event_type in SIGNUP_EVENT_TYPES:
            self._enrich_phase(visitor, event, self.config.signup)
        elif event.event_type in CHECKOUT_EVENT_TYPES:
            self._enrich_phase(visitor, event, self.config.checkout)

    def _enrich_phase(
        self,
        visitor: Visitor,
        event: Event,
        phase: VisitorProfilePhaseConfig,
    ) -> None:
        if not phase.enabled:
            return
        if self.rng.random() > phase.enrichment_probability:
            return

        self._ensure_fields(visitor.profile, phase.fields)
        event.properties.update(_observable_properties(visitor.profile, phase.fields))

    def _ensure_fields(self, profile: VisitorProfile, fields: frozenset[str]) -> None:
        if "first_name" in fields and profile.first_name is None:
            profile.first_name = self.fake.first_name()
        if "last_name" in fields and profile.last_name is None:
            profile.last_name = self.fake.last_name()
        if "email" in fields and profile.email is None:
            self._ensure_identity(profile)
            profile.email = _synthetic_email(
                profile.first_name,
                profile.last_name,
                self.rng,
            )
        if {"shipping_state", "shipping_postal_code"}.intersection(fields) and (
            profile.shipping_state is None or profile.shipping_postal_code is None
        ):
            self._ensure_geography(profile)
        if "phone" in fields and profile.phone is None:
            area_code = self._area_code_for_profile(profile)
            profile.phone = _synthetic_phone(area_code, self.rng)

    def _ensure_identity(self, profile: VisitorProfile) -> None:
        if profile.first_name is None:
            profile.first_name = self.fake.first_name()
        if profile.last_name is None:
            profile.last_name = self.fake.last_name()

    def _ensure_geography(self, profile: VisitorProfile) -> None:
        if (
            profile.shipping_state is not None
            and profile.shipping_postal_code is not None
        ):
            return
        if self.geography is None:
            return
        location = self.geography.sample(self.rng)
        profile.shipping_postal_code = location.zip_code
        profile.shipping_state = location.state

    def _area_code_for_profile(self, profile: VisitorProfile) -> str:
        if self.geography is None:
            return "555"
        if profile.shipping_postal_code is None:
            location = self.geography.sample(self.rng)
            profile.shipping_postal_code = location.zip_code
            profile.shipping_state = location.state
            return location.area_code
        for location in self.geography.records:
            if location.zip_code == profile.shipping_postal_code:
                return location.area_code
        return "555"

    @staticmethod
    def _load_geography(
        config: VisitorProfileConfig,
    ) -> GeographyDistribution | None:
        if not config.geography.enabled:
            return None
        if config.geography.distribution_file is None:
            return None
        return load_geography_distribution(config.geography.distribution_file)


def _observable_properties(
    profile: VisitorProfile,
    fields: frozenset[str],
) -> dict[str, object]:
    return {
        field: value
        for field in fields
        if (value := getattr(profile, field)) is not None
    }


def _synthetic_email(
    first_name: str | None,
    last_name: str | None,
    rng: Random,
) -> str:
    local_first = _email_part(first_name or "customer")
    local_last = _email_part(last_name or "example")
    suffix = rng.randrange(1000, 10000)
    return f"{local_first}.{local_last}{suffix}@example.com"


def _email_part(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _synthetic_phone(area_code: str, rng: Random) -> str:
    return f"{area_code}-555-{rng.randrange(100, 200):04d}"
