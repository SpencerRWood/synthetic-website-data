"""Configuration loading and validation for website simulation."""

from dataclasses import dataclass
from datetime import date, datetime, time
from math import isclose
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import yaml  # type: ignore[import-untyped]


class ConfigurationError(ValueError):
    """Raised when a generator configuration is invalid."""


@dataclass(frozen=True)
class DatasetConfig:
    start: datetime
    end: datetime
    timezone: ZoneInfo
    random_seed: int | None = None


@dataclass(frozen=True)
class WebsiteConfig:
    entry_page: str
    terminal_pages: frozenset[str]
    graph: dict[str, dict[str, float]]


@dataclass(frozen=True)
class ArrivalsConfig:
    maximum_rate_per_hour: float
    hourly_intensity: dict[int, float]


@dataclass(frozen=True)
class SessionsConfig:
    drop_off_probability: float
    max_page_views: int


@dataclass(frozen=True)
class PageViewDelayConfig:
    shape: float
    scale_seconds: float


@dataclass(frozen=True)
class PageViewsConfig:
    delay: PageViewDelayConfig


@dataclass(frozen=True)
class GeneratorConfig:
    dataset: DatasetConfig
    website: WebsiteConfig
    arrivals: ArrivalsConfig
    sessions: SessionsConfig
    page_views: PageViewsConfig


def load_config(path: str | Path) -> GeneratorConfig:
    """Load and validate a YAML generator configuration."""
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigurationError("configuration must be a mapping")
    return parse_config(cast("dict[str, Any]", raw))


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
    arrivals = _parse_arrivals(_required_mapping(raw, "arrivals"))
    sessions = _parse_sessions(_required_mapping(raw, "sessions"))
    page_views = _parse_page_views(_required_mapping(raw, "page_views"))

    return GeneratorConfig(
        dataset=dataset,
        website=website,
        arrivals=arrivals,
        sessions=sessions,
        page_views=page_views,
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


def _parse_website(raw: dict[str, Any]) -> WebsiteConfig:
    entry_page = str(_required(raw, "entry_page"))
    graph = _parse_graph(_required_mapping(raw, "graph"))
    terminal_pages_raw = raw.get("terminal_pages", [])
    if not isinstance(terminal_pages_raw, list):
        raise ConfigurationError("website.terminal_pages must be a list")
    terminal_pages = frozenset(str(page) for page in terminal_pages_raw)

    if entry_page not in graph:
        raise ConfigurationError("website.entry_page must exist in website.graph")

    for terminal_page in terminal_pages:
        if terminal_page not in graph:
            raise ConfigurationError("every terminal page must exist in website.graph")
        if graph[terminal_page]:
            raise ConfigurationError("terminal pages must not have outgoing edges")

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
        graph=graph,
    )


def _parse_arrivals(raw: dict[str, Any]) -> ArrivalsConfig:
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

    return ArrivalsConfig(
        maximum_rate_per_hour=maximum_rate,
        hourly_intensity=hours,
    )


def _parse_sessions(raw: dict[str, Any]) -> SessionsConfig:
    drop_off_probability = float(_required(raw, "drop_off_probability"))
    max_page_views = int(_required(raw, "max_page_views"))
    if not 0 <= drop_off_probability <= 1:
        raise ConfigurationError(
            "sessions.drop_off_probability must be between 0 and 1"
        )
    if max_page_views < 1:
        raise ConfigurationError("sessions.max_page_views must be >= 1")
    return SessionsConfig(
        drop_off_probability=drop_off_probability,
        max_page_views=max_page_views,
    )


def _parse_page_views(raw: dict[str, Any]) -> PageViewsConfig:
    delay = _required_mapping(raw, "delay")
    if delay.get("distribution") != "gamma":
        raise ConfigurationError("page_views.delay.distribution must be gamma")
    shape = float(_required(delay, "shape"))
    scale_seconds = float(_required(delay, "scale_seconds"))
    if shape <= 0:
        raise ConfigurationError("page_views.delay.shape must be > 0")
    if scale_seconds <= 0:
        raise ConfigurationError("page_views.delay.scale_seconds must be > 0")
    return PageViewsConfig(
        delay=PageViewDelayConfig(shape=shape, scale_seconds=scale_seconds)
    )


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


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = _required(raw, key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} must be a mapping")
    return cast("dict[str, Any]", value)
