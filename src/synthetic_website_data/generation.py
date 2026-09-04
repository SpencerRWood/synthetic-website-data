import json
import sys
from pathlib import Path

from synthetic_website_data.campaigns import CampaignSchedule
from synthetic_website_data.config import GeneratorConfig, load_config
from synthetic_website_data.exporters.csv import export_csv, export_csv_with_fields
from synthetic_website_data.exporters.json import export_json
from synthetic_website_data.generators import generate_dataset
from synthetic_website_data.models import SyntheticDataset

DEFAULT_CONFIG_PATH = Path("configs/default.yaml")
DEFAULT_OUTPUT_DIR = Path("data")
CAMPAIGN_ROW_FIELDS = [
    "date_day",
    "campaign_id",
    "channel",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "daily_spend",
    "actual_adstock",
    "actual_saturated_demand",
    "expected_incremental_visitors",
]
WEBSITE_ROW_FIELDS = [
    "from_page",
    "to_page",
    "transition_probability",
]


def visitor_rows(dataset: SyntheticDataset) -> list[dict[str, object]]:
    return [
        {
            "visitor_id": str(visitor.visitor_id),
            "session_count": len(visitor.sessions),
            "acquisition_source": visitor.acquisition_source or "",
            "acquisition_campaign_id": visitor.acquisition_campaign_id or "",
            "acquisition_utm_medium": visitor.acquisition_utm_medium or "",
            "acquisition_utm_campaign": visitor.acquisition_utm_campaign or "",
        }
        for visitor in dataset.visitors
    ]


def session_rows(dataset: SyntheticDataset) -> list[dict[str, object]]:
    return [
        {
            "visitor_id": str(session.visitor_id),
            "session_id": str(session.session_id),
            "session_start_time": session.session_start_time.isoformat(),
            "session_end_time": (
                session.session_end_time.isoformat()
                if session.session_end_time is not None
                else ""
            ),
            "channel": session.channel or "",
            "utm_source": session.utm_source or "",
            "utm_medium": session.utm_medium or "",
            "utm_campaign": session.utm_campaign or "",
            "campaign_id": session.campaign_id or "",
            "event_count": len(session.events),
        }
        for session in dataset.iter_sessions()
    ]


def flatten_events(
    dataset: SyntheticDataset,
    *,
    serialize_properties: bool = False,
) -> list[dict[str, object]]:
    return [
        {
            "event_id": str(event.event_id),
            "visitor_id": str(event.visitor_id),
            "session_id": str(event.session_id),
            "page": event.page,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "properties": (
                json.dumps(
                    event.properties,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if serialize_properties
                else event.properties
            ),
        }
        for event in dataset.iter_events()
    ]


def hierarchical_dataset_rows(dataset: SyntheticDataset) -> list[dict[str, object]]:
    return [
        {
            "visitor_id": str(visitor.visitor_id),
            "acquisition_source": visitor.acquisition_source,
            "acquisition_campaign_id": visitor.acquisition_campaign_id,
            "acquisition_utm_medium": visitor.acquisition_utm_medium,
            "acquisition_utm_campaign": visitor.acquisition_utm_campaign,
            "sessions": [
                {
                    "visitor_id": str(session.visitor_id),
                    "session_id": str(session.session_id),
                    "session_start_time": session.session_start_time.isoformat(),
                    "session_end_time": (
                        session.session_end_time.isoformat()
                        if session.session_end_time is not None
                        else None
                    ),
                    "channel": session.channel,
                    "utm_source": session.utm_source,
                    "utm_medium": session.utm_medium,
                    "utm_campaign": session.utm_campaign,
                    "campaign_id": session.campaign_id,
                    "events": [
                        {
                            "event_id": str(event.event_id),
                            "visitor_id": str(event.visitor_id),
                            "session_id": str(event.session_id),
                            "page": event.page,
                            "timestamp": event.timestamp.isoformat(),
                            "event_type": event.event_type,
                            "properties": event.properties,
                        }
                        for event in session.events
                    ],
                }
                for session in visitor.sessions
            ],
        }
        for visitor in dataset.visitors
    ]


def campaign_rows(config: GeneratorConfig) -> list[dict[str, object]]:
    """Return calculated daily campaign rows for warehouse loading."""
    schedule = CampaignSchedule.build(
        config.campaigns,
        config.dataset.start,
        config.dataset.end,
    )
    return [
        {
            "date_day": day.isoformat(),
            "campaign_id": effect.campaign_id,
            "channel": effect.channel,
            "utm_source": effect.utm_source,
            "utm_medium": effect.utm_medium,
            "utm_campaign": effect.utm_campaign,
            "daily_spend": round(effect.daily_spend, 6),
            "actual_adstock": round(effect.adstock, 6),
            "actual_saturated_demand": round(effect.saturated_demand, 6),
            "expected_incremental_visitors": round(
                effect.incremental_visitors,
                6,
            ),
        }
        for day in sorted(schedule.effects_by_day)
        for effect in schedule.effects_by_day[day]
    ]


def website_rows(config: GeneratorConfig) -> list[dict[str, object]]:
    """Return the configured directed website graph as relational edge rows."""
    return [
        {
            "from_page": from_page,
            "to_page": to_page,
            "transition_probability": round(probability, 6),
        }
        for from_page, destinations in sorted(config.website.graph.items())
        for to_page, probability in sorted(destinations.items())
    ]


def generate_and_export(
    config_path: str | Path,
    output_dir: str | Path = "data",
) -> dict[str, Path]:
    """Generate a dataset from YAML config and export flat/hierarchical files."""
    config = load_config(Path(config_path))
    dataset = generate_dataset(config)
    destination = Path(output_dir)

    outputs = {
        "visitors_csv": destination / "visitors.csv",
        "sessions_csv": destination / "sessions.csv",
        "events_csv": destination / "events.csv",
        "campaigns_csv": destination / "campaigns.csv",
        "website_csv": destination / "website.csv",
        "dataset_json": destination / "dataset.json",
        "events_json": destination / "events.json",
    }
    export_csv(visitor_rows(dataset), outputs["visitors_csv"])
    export_csv(session_rows(dataset), outputs["sessions_csv"])
    export_csv(
        flatten_events(dataset, serialize_properties=True),
        outputs["events_csv"],
    )
    export_csv_with_fields(
        campaign_rows(config),
        outputs["campaigns_csv"],
        CAMPAIGN_ROW_FIELDS,
    )
    export_csv_with_fields(
        website_rows(config),
        outputs["website_csv"],
        WEBSITE_ROW_FIELDS,
    )
    export_json(hierarchical_dataset_rows(dataset), outputs["dataset_json"])
    export_json(flatten_events(dataset), outputs["events_json"])
    return outputs


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 2:
        raise SystemExit("usage: python src/main.py [path/to/config.yaml] [output_dir]")

    config_path = Path(args[0]) if args else DEFAULT_CONFIG_PATH
    output_dir = Path(args[1]) if len(args) == 2 else DEFAULT_OUTPUT_DIR
    outputs = generate_and_export(config_path, output_dir)
    for label, path in outputs.items():
        sys.stdout.write(f"{label}\t{path}\n")


if __name__ == "__main__":
    main()
