"""SQLAlchemy Core metadata for raw PostgreSQL tables."""

from sqlalchemy import (
    Column,
    Date,
    Index,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

metadata = MetaData()

events = Table(
    "events",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("visitor_id", UUID(as_uuid=True), nullable=False),
    Column("session_id", UUID(as_uuid=True), nullable=False),
    Column("page", Text, nullable=False),
    Column("timestamp", TIMESTAMP(timezone=True), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("properties", JSONB, nullable=False),
    PrimaryKeyConstraint("event_id", name="pk_raw_events"),
    Index("ix_raw_events_visitor_id", "visitor_id"),
    Index("ix_raw_events_session_id_timestamp", "session_id", "timestamp"),
    Index("ix_raw_events_timestamp", "timestamp"),
    schema="raw",
)

campaigns = Table(
    "campaigns",
    metadata,
    Column("date_day", Date, nullable=False),
    Column("campaign_id", Text, nullable=False),
    Column("channel", Text, nullable=False),
    Column("utm_source", Text, nullable=False),
    Column("utm_medium", Text, nullable=False),
    Column("utm_campaign", Text, nullable=False),
    Column("daily_spend", Numeric, nullable=False),
    Column("actual_adstock", Numeric, nullable=False),
    Column("actual_saturated_demand", Numeric, nullable=False),
    Column("expected_incremental_visitors", Numeric, nullable=False),
    PrimaryKeyConstraint("date_day", "campaign_id", name="pk_raw_campaigns"),
    Index("ix_raw_campaigns_campaign_id", "campaign_id"),
    Index("ix_raw_campaigns_date_day", "date_day"),
    schema="raw",
)
