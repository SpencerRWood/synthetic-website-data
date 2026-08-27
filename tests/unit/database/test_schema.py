from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB

from synthetic_website_data.database.schema import events


def test_raw_events_schema_includes_event_type_and_properties() -> None:
    assert isinstance(events.c.event_type.type, Text)
    assert isinstance(events.c.properties.type, JSONB)
    assert not events.c.event_type.nullable
    assert not events.c.properties.nullable
