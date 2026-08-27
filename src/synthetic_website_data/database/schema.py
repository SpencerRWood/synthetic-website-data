"""SQLAlchemy Core metadata for raw PostgreSQL tables."""

from sqlalchemy import Column, Index, MetaData, PrimaryKeyConstraint, Table, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

metadata = MetaData()

events = Table(
    "events",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("visitor_id", UUID(as_uuid=True), nullable=False),
    Column("session_id", UUID(as_uuid=True), nullable=False),
    Column("page", Text, nullable=False),
    Column("timestamp", TIMESTAMP(timezone=True), nullable=False),
    PrimaryKeyConstraint("event_id", name="pk_raw_events"),
    Index("ix_raw_events_visitor_id", "visitor_id"),
    Index("ix_raw_events_session_id_timestamp", "session_id", "timestamp"),
    Index("ix_raw_events_timestamp", "timestamp"),
    schema="raw",
)
