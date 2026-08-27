"""Configuration loading and validation for website simulation."""

from dataclasses import dataclass
from datetime import date, datetime, time
from math import isclose, isfinite
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import yaml  # type: ignore[import-untyped]


class ConfigurationError(ValueError):
    """Raised when a generator configuration is invalid."""


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigurationError(f"duplicate configuration key: {key!r}")
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class DatasetConfig:
    start: datetime
    end: datetime
    timezone: ZoneInfo
    random_seed: int | None = None


@dataclass(frozen=True)
class PageViewDelayConfig:
    shape: float
    scale_seconds: float


@dataclass(frozen=True)
class PageBehaviorConfig:
    drop_off_probability: float | None = None
    delay: PageViewDelayConfig | None = None
    event_type: str | None = None


@dataclass(frozen=True)
class WebsiteConfig:
    entry_page: str
    terminal_pages: frozenset[str]
    conversion_pages: frozenset[str]
    pages: dict[str, PageBehaviorConfig]
    graph: dict[str, dict[str, float]]


@dataclass(frozen=True)
class ArrivalsConfig:
    maximum_rate_per_hour: float
    hourly_intensity: dict[int, float]
    weekday_intensity: dict[str, float]
    annual_growth_rate: float = 0.0


@dataclass(frozen=True)
class SessionsConfig:
    default_drop_off_probability: float
    max_page_views: int

    @property
    def drop_off_probability(self) -> float:
        """Backward-compatible alias for the default drop-off probability."""
        return self.default_drop_off_probability


@dataclass(frozen=True)
class PageViewsConfig:
    default_delay: PageViewDelayConfig

    @property
    def delay(self) -> PageViewDelayConfig:
        """Backward-compatible alias for the default page-view delay."""
        return self.default_delay


@dataclass(frozen=True)
class VisitorsConfig:
    returning_visitor_rate: float = 0.0
    max_sessions_per_visitor: int = 1


PropertySpecKind = Literal["choice", "float", "id", "integer", "literal"]


@dataclass(frozen=True)
class EventPropertySpec:
    kind: PropertySpecKind
    value: object = None
    values: tuple[object, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    decimals: int = 2
    prefix: str = ""


@dataclass(frozen=True)
class EventPropertiesConfig:
    event_types: dict[str, dict[str, EventPropertySpec]]


@dataclass(frozen=True)
class GeneratorConfig:
    dataset: DatasetConfig
    website: WebsiteConfig
    arrivals: ArrivalsConfig
    sessions: SessionsConfig
    page_views: PageViewsConfig
    visitors: VisitorsConfig
    event_properties: EventPropertiesConfig


def load_config(path: str | Path) -> GeneratorConfig:
    """Load and validate a YAML generator configuration."""
    config_path = Path(path)
    raw = _load_yaml_mapping(config_path, "configuration")
    raw = _resolve_website_graph_reference(raw, config_path.parent)
    raw = _resolve_event_properties_reference(raw, config_path.parent)
    return parse_config(raw)


def _load_yaml_mapping(path: Path, description: str) -> dict[str, Any]:
    raw = yaml.load(
        path.read_text(encoding="utf-8"),
        Loader=_UniqueKeySafeLoader,  # noqa: S506
    )
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{description} must be a mapping")
    return cast("dict[str, Any]", raw)


def _resolve_website_graph_reference(
    raw: dict[str, Any],
    base_path: Path,
) -> dict[str, Any]:
    website = _required_mapping(raw, "website")
    graph_path = website.pop("graph_path", None)
    if graph_path is None:
        return raw
    if "graph" in website:
        raise ConfigurationError(
            "website.graph and website.graph_path cannot both be configured"
        )

    graph_config_path = Path(str(graph_path))
    if not graph_config_path.is_absolute():
        graph_config_path = base_path / graph_config_path
    graph_config = _load_yaml_mapping(graph_config_path, "website graph configuration")
    website["graph"] = _required_mapping(graph_config, "graph")
    website["pages"] = _merge_page_configs(
        graph_config.get("pages", {}),
        website.get("pages", {}),
    )
    return raw


def _merge_page_configs(
    base_value: object,
    override_value: object,
) -> dict[str, Any]:
    base = _optional_mapping(base_value, "website.pages")
    override = _optional_mapping(override_value, "website.pages")
    merged: dict[str, Any] = {}
    for page, config in base.items():
        if config is None:
            merged[str(page)] = {}
        elif not isinstance(config, dict):
            raise ConfigurationError("website.pages.* must be a mapping")
        else:
            merged[str(page)] = dict(cast("dict[str, Any]", config))
    for page, config in override.items():
        if config is None:
            merged[str(page)] = {}
        elif not isinstance(config, dict):
            raise ConfigurationError("website.pages.* must be a mapping")
        else:
            existing = merged.get(str(page), {})
            merged[str(page)] = {**existing, **cast("dict[str, Any]", config)}
    return merged


def _resolve_event_properties_reference(
    raw: dict[str, Any],
    base_path: Path,
) -> dict[str, Any]:
    properties_path = raw.pop("event_properties_path", None)
    if properties_path is None:
        return raw
    if "event_properties" in raw:
        raise ConfigurationError(
            "event_properties and event_properties_path cannot both be configured"
        )

    properties_config_path = Path(str(properties_path))
    if not properties_config_path.is_absolute():
        properties_config_path = base_path / properties_config_path
    properties_config = _load_yaml_mapping(
        properties_config_path,
        "event properties configuration",
    )
    raw["event_properties"] = _required_mapping(
        properties_config,
        "event_properties",
    )
    return raw


def parse_config(raw: dict[str, Any]) -> GeneratorConfig:
    """Parse and validate raw configuration data."""
    try:
        timezone = ZoneInfo(str(_required_mapping(raw, "dataset")["timezone"]))
    except KeyError as error:
        raise ConfigurationError("dataset.timezone is required") from error
    except Exception as error:
        raise ConfigurationError("dataset.timezone must be a valid timezone") from error

    dataset = _parse_dataset(_required_mapping(raw, "dataset"), timezone)
    website = _parse_website(_required_mapping(raw, "website"))
    arrivals = _parse_arrivals(_required_mapping(raw, "arrivals"), dataset)
    sessions = _parse_sessions(_required_mapping(raw, "sessions"))
    page_views = _parse_page_views(_required_mapping(raw, "page_views"))
    visitors = _parse_visitors(raw.get("visitors", {}))
    event_properties = _parse_event_properties(raw.get("event_properties", {}))

    return GeneratorConfig(
        dataset=dataset,
        website=website,
        arrivals=arrivals,
        sessions=sessions,
        page_views=page_views,
        visitors=visitors,
        event_properties=event_properties,
    )


def _parse_dataset(raw: dict[str, Any], timezone: ZoneInfo) -> DatasetConfig:
    start = _parse_datetime(_required(raw, "start_date"), timezone, "start_date")
    end = _parse_datetime(_required(raw, "end_date"), timezone, "end_date")
    if start >= end:
        raise ConfigurationError("dataset.start_date must be before dataset.end_date")

    seed = raw.get("random_seed")
    if seed is not None and not isinstance(seed, int):
        raise ConfigurationError("dataset.random_seed must be an integer")
    return DatasetConfig(start=start, end=end, timezone=timezone, random_seed=seed)


def _parse_website(raw: dict[str, Any]) -> WebsiteConfig:  # noqa: PLR0912
    entry_page = str(_required(raw, "entry_page"))
    graph = _parse_graph(_required_mapping(raw, "graph"))
    terminal_pages_raw = raw.get("terminal_pages", [])
    if not isinstance(terminal_pages_raw, list):
        raise ConfigurationError("website.terminal_pages must be a list")
    terminal_pages = frozenset(str(page) for page in terminal_pages_raw)
    conversion_pages_raw = raw.get("conversion_pages", [])
    if not isinstance(conversion_pages_raw, list):
        raise ConfigurationError("website.conversion_pages must be a list")
    conversion_pages = frozenset(str(page) for page in conversion_pages_raw)
    pages = _parse_page_behaviors(raw.get("pages", {}))

    if entry_page not in graph:
        raise ConfigurationError("website.entry_page must exist in website.graph")

    for terminal_page in terminal_pages:
        if terminal_page not in graph:
            raise ConfigurationError("every terminal page must exist in website.graph")
        if graph[terminal_page]:
            raise ConfigurationError("terminal pages must not have outgoing edges")

    for conversion_page in conversion_pages:
        if conversion_page not in graph:
            raise ConfigurationError(
                "every conversion page must exist in website.graph"
            )

    for page in pages:
        if page not in graph:
            raise ConfigurationError(
                "website.pages overrides must exist in website.graph"
            )

    for source, edges in graph.items():
        for destination, probability in edges.items():
            if destination not in graph:
                raise ConfigurationError(
                    f"website graph edge {source!r}->{destination!r} "
                    "references a missing destination"
                )
            if not 0 <= probability <= 1:
                raise ConfigurationError(
                    "website graph transition probabilities must be between 0 and 1"
                )
        if source not in terminal_pages and not edges:
            raise ConfigurationError("non-terminal pages must have outgoing edges")
        if source not in terminal_pages and not isclose(sum(edges.values()), 1.0):
            raise ConfigurationError(
                f"outgoing transition probabilities for {source!r} must sum to 1.0"
            )

    return WebsiteConfig(
        entry_page=entry_page,
        terminal_pages=terminal_pages,
        conversion_pages=conversion_pages,
        pages=pages,
        graph=graph,
    )


WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

SECONDS_PER_YEAR = 365.2425 * 24 * 60 * 60


def _parse_arrivals(raw: dict[str, Any], dataset: DatasetConfig) -> ArrivalsConfig:
    maximum_rate = float(_required(raw, "maximum_rate_per_hour"))
    if maximum_rate <= 0:
        raise ConfigurationError("arrivals.maximum_rate_per_hour must be > 0")

    hourly_raw = _required_mapping(raw, "hourly_intensity")
    hours = {int(hour): float(intensity) for hour, intensity in hourly_raw.items()}
    expected_hours = set(range(24))
    if set(hours) != expected_hours:
        raise ConfigurationError("arrivals.hourly_intensity must define hours 0-23")
    for intensity in hours.values():
        if not 0 <= intensity <= 1:
            raise ConfigurationError(
                "arrival hourly intensities must be between 0 and 1"
            )

    weekday_raw = _required_mapping(raw, "weekday_intensity")
    weekday_intensities = {
        str(weekday).lower(): float(intensity)
        for weekday, intensity in weekday_raw.items()
    }
    if set(weekday_intensities) != set(WEEKDAY_NAMES):
        raise ConfigurationError(
            "arrivals.weekday_intensity must define exactly monday through sunday"
        )
    for intensity in weekday_intensities.values():
        if not 0 <= intensity <= 1:
            raise ConfigurationError(
                "arrival weekday intensities must be between 0 and 1"
            )

    annual_growth_rate = float(_required(raw, "annual_growth_rate"))
    if not isfinite(annual_growth_rate):
        raise ConfigurationError("arrivals.annual_growth_rate must be finite")
    duration_years = (dataset.end - dataset.start).total_seconds() / SECONDS_PER_YEAR
    trend_end_demand = 1.0 + annual_growth_rate * duration_years
    if trend_end_demand < 0:
        raise ConfigurationError(
            "arrivals.annual_growth_rate would make trend intensity negative"
        )

    return ArrivalsConfig(
        maximum_rate_per_hour=maximum_rate,
        hourly_intensity=hours,
        weekday_intensity=weekday_intensities,
        annual_growth_rate=annual_growth_rate,
    )


def _parse_sessions(raw: dict[str, Any]) -> SessionsConfig:
    drop_off_probability = float(
        _required_one_of(raw, "default_drop_off_probability", "drop_off_probability")
    )
    max_page_views = int(_required(raw, "max_page_views"))
    if not 0 <= drop_off_probability <= 1:
        raise ConfigurationError(
            "sessions.default_drop_off_probability must be between 0 and 1"
        )
    if max_page_views < 1:
        raise ConfigurationError("sessions.max_page_views must be >= 1")
    return SessionsConfig(
        default_drop_off_probability=drop_off_probability,
        max_page_views=max_page_views,
    )


def _parse_page_views(raw: dict[str, Any]) -> PageViewsConfig:
    delay = _required_mapping_one_of(raw, "default_delay", "delay")
    if delay.get("distribution") != "gamma":
        raise ConfigurationError("page_views.default_delay.distribution must be gamma")
    return PageViewsConfig(
        default_delay=_parse_delay(delay, "page_views.default_delay")
    )


def _parse_visitors(raw_value: object) -> VisitorsConfig:
    if not isinstance(raw_value, dict):
        raise ConfigurationError("visitors must be a mapping")
    raw = cast("dict[str, Any]", raw_value)
    returning_visitor_rate = float(raw.get("returning_visitor_rate", 0.0))
    max_sessions_per_visitor = int(raw.get("max_sessions_per_visitor", 1))
    if not 0 <= returning_visitor_rate <= 1:
        raise ConfigurationError(
            "visitors.returning_visitor_rate must be between 0 and 1"
        )
    if max_sessions_per_visitor < 1:
        raise ConfigurationError("visitors.max_sessions_per_visitor must be >= 1")
    return VisitorsConfig(
        returning_visitor_rate=returning_visitor_rate,
        max_sessions_per_visitor=max_sessions_per_visitor,
    )


def _parse_event_properties(raw_value: object) -> EventPropertiesConfig:
    if raw_value is None:
        return EventPropertiesConfig(event_types={})
    if not isinstance(raw_value, dict):
        raise ConfigurationError("event_properties must be a mapping")

    event_types: dict[str, dict[str, EventPropertySpec]] = {}
    for event_type, raw_properties in cast("dict[str, Any]", raw_value).items():
        if not isinstance(raw_properties, dict):
            raise ConfigurationError("event_properties.* must be a mapping")
        properties: dict[str, EventPropertySpec] = {}
        for property_name, raw_spec in raw_properties.items():
            properties[str(property_name)] = _parse_event_property_spec(
                cast("object", raw_spec),
                f"event_properties.{event_type}.{property_name}",
            )
        event_types[str(event_type)] = properties
    return EventPropertiesConfig(event_types=event_types)


def _parse_event_property_spec(
    raw_value: object,
    field_name: str,
) -> EventPropertySpec:
    if not isinstance(raw_value, dict):
        return EventPropertySpec(kind="literal", value=raw_value)
    raw = cast("dict[str, Any]", raw_value)
    raw_kind = str(_required(raw, "type"))
    if raw_kind == "choice":
        values = raw.get("values")
        if not isinstance(values, list) or not values:
            raise ConfigurationError(f"{field_name}.values must be a non-empty list")
        return EventPropertySpec(kind="choice", values=tuple(values))
    if raw_kind == "float":
        minimum = float(_required(raw, "min"))
        maximum = float(_required(raw, "max"))
        decimals = int(raw.get("decimals", 2))
        _validate_numeric_range(minimum, maximum, field_name)
        if decimals < 0:
            raise ConfigurationError(f"{field_name}.decimals must be >= 0")
        return EventPropertySpec(
            kind="float",
            minimum=minimum,
            maximum=maximum,
            decimals=decimals,
        )
    if raw_kind == "id":
        minimum = float(int(_required(raw, "min")))
        maximum = float(int(_required(raw, "max")))
        _validate_numeric_range(minimum, maximum, field_name)
        return EventPropertySpec(
            kind="id",
            minimum=minimum,
            maximum=maximum,
            prefix=str(raw.get("prefix", "")),
        )
    if raw_kind == "integer":
        minimum = float(int(_required(raw, "min")))
        maximum = float(int(_required(raw, "max")))
        _validate_numeric_range(minimum, maximum, field_name)
        return EventPropertySpec(kind="integer", minimum=minimum, maximum=maximum)
    if raw_kind == "literal":
        return EventPropertySpec(kind="literal", value=raw.get("value"))
    raise ConfigurationError(
        f"{field_name}.type must be choice, float, id, integer, or literal"
    )


def _validate_numeric_range(minimum: float, maximum: float, field_name: str) -> None:
    if minimum > maximum:
        raise ConfigurationError(f"{field_name}.min must be <= max")


def _parse_page_behaviors(raw_value: object) -> dict[str, PageBehaviorConfig]:
    if raw_value is None:
        return {}
    if not isinstance(raw_value, dict):
        raise ConfigurationError("website.pages must be a mapping")

    pages: dict[str, PageBehaviorConfig] = {}
    for page, raw_page_config in cast("dict[str, Any]", raw_value).items():
        page_config = {} if raw_page_config is None else raw_page_config
        if not isinstance(page_config, dict):
            raise ConfigurationError("website.pages.* must be a mapping")
        page_name = str(page)
        drop_off_probability = page_config.get("drop_off_probability")
        if drop_off_probability is not None:
            drop_off_probability = float(drop_off_probability)
            if not 0 <= drop_off_probability <= 1:
                raise ConfigurationError(
                    "website.pages.*.drop_off_probability must be between 0 and 1"
                )
        delay = None
        if "delay" in page_config:
            delay_raw = page_config["delay"]
            if not isinstance(delay_raw, dict):
                raise ConfigurationError("website.pages.*.delay must be a mapping")
            delay = _parse_delay(
                cast("dict[str, Any]", delay_raw),
                "website.pages.*.delay",
                require_distribution=False,
            )
        event_type_raw = page_config.get("event_type")
        event_type = None
        if event_type_raw is not None:
            event_type = str(event_type_raw)
            if not event_type:
                raise ConfigurationError("website.pages.*.event_type must not be empty")
        pages[page_name] = PageBehaviorConfig(
            drop_off_probability=drop_off_probability,
            delay=delay,
            event_type=event_type,
        )
    return pages


def _parse_delay(
    delay: dict[str, Any],
    field_name: str,
    *,
    require_distribution: bool = True,
) -> PageViewDelayConfig:
    if require_distribution and delay.get("distribution") != "gamma":
        raise ConfigurationError(f"{field_name}.distribution must be gamma")
    if "distribution" in delay and delay["distribution"] != "gamma":
        raise ConfigurationError(f"{field_name}.distribution must be gamma")
    shape = float(_required(delay, "shape"))
    scale_seconds = float(_required(delay, "scale_seconds"))
    if shape <= 0:
        raise ConfigurationError(f"{field_name}.shape must be > 0")
    if scale_seconds <= 0:
        raise ConfigurationError(f"{field_name}.scale_seconds must be > 0")
    return PageViewDelayConfig(shape=shape, scale_seconds=scale_seconds)


def _parse_graph(raw: dict[str, Any]) -> dict[str, dict[str, float]]:
    graph: dict[str, dict[str, float]] = {}
    for source, raw_edges in raw.items():
        edge_mapping = {} if raw_edges is None else raw_edges
        if not isinstance(edge_mapping, dict):
            raise ConfigurationError("website.graph nodes must map to edge mappings")
        graph[str(source)] = {
            str(destination): float(probability)
            for destination, probability in edge_mapping.items()
        }
    return graph


def _parse_datetime(value: object, timezone: ZoneInfo, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise ConfigurationError(f"dataset.{field_name} must be a date or datetime")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _required(raw: dict[str, Any], key: str) -> Any:
    if key not in raw:
        raise ConfigurationError(f"{key} is required")
    return raw[key]


def _required_one_of(raw: dict[str, Any], preferred_key: str, legacy_key: str) -> Any:
    if preferred_key in raw:
        return raw[preferred_key]
    if legacy_key in raw:
        return raw[legacy_key]
    raise ConfigurationError(f"{preferred_key} is required")


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = _required(raw, key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} must be a mapping")
    return cast("dict[str, Any]", value)


def _optional_mapping(value: object, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{field_name} must be a mapping")
    return cast("dict[str, Any]", value)


def _required_mapping_one_of(
    raw: dict[str, Any],
    preferred_key: str,
    legacy_key: str,
) -> dict[str, Any]:
    value = _required_one_of(raw, preferred_key, legacy_key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"{preferred_key} must be a mapping")
    return cast("dict[str, Any]", value)
