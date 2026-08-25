import sys
from pathlib import Path

from synthetic_website_data.config import load_config
from synthetic_website_data.exporters.csv import export_csv
from synthetic_website_data.exporters.json import export_json
from synthetic_website_data.generators import generate_dataset
from synthetic_website_data.models import SyntheticDataset

DEFAULT_CONFIG_PATH = Path("configs/default.yaml")
DEFAULT_OUTPUT_DIR = Path("data")


def visitor_rows(dataset: SyntheticDataset) -> list[dict[str, object]]:
    return [
        {
            "visitor_id": str(visitor.visitor_id),
            "session_count": len(visitor.sessions),
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
            "event_count": len(session.events),
        }
        for session in dataset.sessions
    ]


def flatten_events(dataset: SyntheticDataset) -> list[dict[str, object]]:
    return [
        {
            "visitor_id": str(event.visitor_id),
            "session_id": str(event.session_id),
            "event_id": str(event.event_id),
            "page": event.page,
            "timestamp": event.timestamp.isoformat(),
        }
        for event in dataset.events
    ]


def hierarchical_dataset_rows(dataset: SyntheticDataset) -> list[dict[str, object]]:
    return [
        {
            "visitor_id": str(visitor.visitor_id),
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
                    "events": [
                        {
                            "event_id": str(event.event_id),
                            "visitor_id": str(event.visitor_id),
                            "session_id": str(event.session_id),
                            "page": event.page,
                            "timestamp": event.timestamp.isoformat(),
                        }
                        for event in session.events
                    ],
                }
                for session in visitor.sessions
            ],
        }
        for visitor in dataset.visitors
    ]


def generate_and_export(
    config_path: str | Path,
    output_dir: str | Path = "data",
) -> dict[str, Path]:
    """Generate a dataset from YAML config and export flat/hierarchical files."""
    dataset = generate_dataset(load_config(Path(config_path)))
    destination = Path(output_dir)

    outputs = {
        "visitors_csv": destination / "visitors.csv",
        "sessions_csv": destination / "sessions.csv",
        "events_csv": destination / "events.csv",
        "dataset_json": destination / "dataset.json",
        "events_json": destination / "events.json",
    }
    export_csv(visitor_rows(dataset), outputs["visitors_csv"])
    export_csv(session_rows(dataset), outputs["sessions_csv"])
    export_csv(flatten_events(dataset), outputs["events_csv"])
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
