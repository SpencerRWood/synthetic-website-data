"""Website graph traversal and page-view timing helpers."""

from datetime import datetime, timedelta
from random import Random

from .config import PageViewDelayConfig, WebsiteConfig


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


def traverse_session_pages(  # noqa: PLR0913
    *,
    website: WebsiteConfig,
    delay: PageViewDelayConfig,
    drop_off_probability: float,
    max_page_views: int,
    start_time: datetime,
    end_time: datetime,
    rng: Random,
) -> list[tuple[str, datetime]]:
    """Generate page/timestamp pairs for one website session."""
    page_views = [(website.entry_page, start_time)]
    current_page = website.entry_page
    current_timestamp = start_time

    while len(page_views) < max_page_views:
        if current_page in website.terminal_pages:
            break
        if rng.random() < drop_off_probability:
            break

        edges = website.graph[current_page]
        if not edges:
            break

        next_page = select_next_page(edges, rng)
        next_timestamp = current_timestamp + sample_page_view_delay(delay, rng)
        if next_timestamp >= end_time:
            break

        page_views.append((next_page, next_timestamp))
        current_page = next_page
        current_timestamp = next_timestamp

    return page_views
