"""Generate website data files and replace raw PostgreSQL events."""

import sys
from collections.abc import Sequence
from pathlib import Path

from alembic import command
from alembic.config import Config

from main import DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_DIR, generate_and_export
from synthetic_website_data.database.loader import (
    load_campaigns_csv,
    load_events_csv,
    load_website_csv,
)


def progress(message: str) -> None:
    sys.stdout.write(f"[synthetic-website-data] {message}\n")
    sys.stdout.flush()


def run_generate_and_load(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    """Generate output files, migrate PostgreSQL, and replace raw.events."""
    config = Path(config_path)
    destination = Path(output_dir)

    progress(f"Generating dataset from {config}")
    outputs = generate_and_export(config, destination)
    for label, path in outputs.items():
        progress(f"Wrote {label}: {path}")

    progress("Applying Alembic migrations")
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    progress("Replacing raw.events with generated events.csv")
    loaded_rows = load_events_csv(
        outputs["events_csv"],
        replace=True,
        progress=progress,
    )
    progress(f"Loaded rows into raw.events: {loaded_rows}")

    progress("Replacing raw.campaigns with generated campaigns.csv")
    loaded_campaign_rows = load_campaigns_csv(
        outputs["campaigns_csv"],
        replace=True,
        progress=progress,
    )
    progress(f"Loaded rows into raw.campaigns: {loaded_campaign_rows}")

    progress("Replacing raw.website with generated website.csv")
    loaded_website_rows = load_website_csv(
        outputs["website_csv"],
        replace=True,
        progress=progress,
    )
    progress(f"Loaded rows into raw.website: {loaded_website_rows}")
    progress("Done")

    return outputs


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 2:
        raise SystemExit(
            "usage: python -m synthetic_website_data.generate_and_load "
            "[path/to/config.yaml] [output_dir]"
        )

    config_path = Path(args[0]) if args else DEFAULT_CONFIG_PATH
    output_dir = Path(args[1]) if len(args) == 2 else DEFAULT_OUTPUT_DIR
    run_generate_and_load(config_path, output_dir)


if __name__ == "__main__":
    main()
