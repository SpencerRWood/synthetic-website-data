"""Website graph traversal and page-view timing helpers."""

from datetime import datetime, timedelta
from random import Random

from .config import PageViewDelayConfig, PageViewsConfig, SessionsConfig, WebsiteConfig


def select_next_page(edges: dict[str, float], rng: Random) -> str:
    """Select the next page according to weighted outgoing edges."""
    threshold = rng.random()
    cumulative = 0.0
    last_page = ""
    for page, probability in edges.items():
        cumulative += probability
        last_page = page
        if threshold <= cumulative:
            return page
    return last_page


def sample_page_view_delay(config: PageViewDelayConfig, rng: Random) -> timedelta:
    """Sample a gamma-distributed page-view delay."""
    return timedelta(
        seconds=rng.gammavariate(
            alpha=config.shape,
            beta=config.scale_seconds,
        )
    )


def drop_off_probability_for_page(
    website: WebsiteConfig,
    sessions: SessionsConfig,
    page: str,
) -> float:
    """Return the page-specific drop-off probability or the session default."""
    page_config = website.pages.get(page)
    if page_config is not None and page_config.drop_off_probability is not None:
        return page_config.drop_off_probability
    return sessions.default_drop_off_probability


def delay_for_page(
    website: WebsiteConfig,
    page_views: PageViewsConfig,
    page: str,
) -> PageViewDelayConfig:
    """Return the current page's dwell-time delay or the global default."""
    page_config = website.pages.get(page)
    if page_config is not None and page_config.delay is not None:
        return page_config.delay
    return page_views.default_delay


def traverse_session_pages(  # noqa: PLR0913
    *,
    website: WebsiteConfig,
    page_view_config: PageViewsConfig,
    sessions: SessionsConfig,
    max_page_views: int,
    start_time: datetime,
    end_time: datetime,
    rng: Random,
) -> list[tuple[str, datetime]]:
    """Generate page/timestamp pairs for one website session."""
    generated_page_views = [(website.entry_page, start_time)]
    current_page = website.entry_page
    current_timestamp = start_time

    while len(generated_page_views) < max_page_views:
        if current_page in website.terminal_pages:
            break
        drop_off_probability = drop_off_probability_for_page(
            website,
            sessions,
            current_page,
        )
        if rng.random() < drop_off_probability:
            break

        edges = website.graph[current_page]
        if not edges:
            break

        next_page = select_next_page(edges, rng)
        next_timestamp = current_timestamp + sample_page_view_delay(
            delay_for_page(website, page_view_config, current_page),
            rng,
        )
        if next_timestamp >= end_time:
            break

        generated_page_views.append((next_page, next_timestamp))
        current_page = next_page
        current_timestamp = next_timestamp

    return generated_page_views
