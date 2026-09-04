from sqlalchemy import Date, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB

from synthetic_website_data.database.schema import campaigns, events, website


def test_raw_events_schema_includes_event_type_and_properties() -> None:
    assert isinstance(events.c.event_type.type, Text)
    assert isinstance(events.c.properties.type, JSONB)
    assert not events.c.event_type.nullable
    assert not events.c.properties.nullable


def test_raw_campaigns_schema_includes_daily_calculated_metrics() -> None:
    assert isinstance(campaigns.c.date_day.type, Date)
    assert isinstance(campaigns.c.campaign_id.type, Text)
    assert isinstance(campaigns.c.channel.type, Text)
    assert isinstance(campaigns.c.utm_source.type, Text)
    assert isinstance(campaigns.c.utm_medium.type, Text)
    assert isinstance(campaigns.c.utm_campaign.type, Text)
    assert isinstance(campaigns.c.daily_spend.type, Numeric)
    assert isinstance(campaigns.c.actual_adstock.type, Numeric)
    assert isinstance(campaigns.c.actual_saturated_demand.type, Numeric)
    assert isinstance(campaigns.c.expected_incremental_visitors.type, Numeric)
    assert not campaigns.c.campaign_id.nullable
    assert not campaigns.c.date_day.nullable


def test_raw_website_schema_includes_directed_graph_edges() -> None:
    assert isinstance(website.c.from_page.type, Text)
    assert isinstance(website.c.to_page.type, Text)
    assert isinstance(website.c.transition_probability.type, Numeric)
    assert not website.c.from_page.nullable
    assert not website.c.to_page.nullable
