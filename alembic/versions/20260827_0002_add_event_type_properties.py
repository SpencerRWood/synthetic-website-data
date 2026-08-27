"""Add event type and properties to raw events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_0002"
down_revision: str | None = "20260826_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "event_type",
            sa.Text(),
            server_default="page_view",
            nullable=False,
        ),
        schema="raw",
    )
    op.add_column(
        "events",
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        schema="raw",
    )
    op.alter_column("events", "event_type", server_default=None, schema="raw")
    op.alter_column("events", "properties", server_default=None, schema="raw")


def downgrade() -> None:
    op.drop_column("events", "properties", schema="raw")
    op.drop_column("events", "event_type", schema="raw")
