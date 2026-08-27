"""Load generated event CSVs into PostgreSQL."""

import sys

from synthetic_website_data.database.loader import _load_events_csv_from_args


def main(argv: list[str] | None = None) -> None:
    row_count = _load_events_csv_from_args(sys.argv[1:] if argv is None else argv)
    sys.stdout.write(f"loaded_rows\t{row_count}\n")


if __name__ == "__main__":
    main()
