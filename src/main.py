"""Backward-compatible script entry point for data generation."""

import sys
from collections.abc import Sequence
from pathlib import Path

from synthetic_website_data.generation import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    generate_and_export,
)

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_OUTPUT_DIR",
    "generate_and_export",
]


def main(argv: Sequence[str] | None = None) -> None:
    """Generate exports using the original positional-argument interface."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 2:
        raise SystemExit("usage: python src/main.py [path/to/config.yaml] [output_dir]")

    config_path = Path(args[0]) if args else DEFAULT_CONFIG_PATH
    output_dir = Path(args[1]) if len(args) == 2 else DEFAULT_OUTPUT_DIR
    for label, path in generate_and_export(config_path, output_dir).items():
        sys.stdout.write(f"{label}\t{path}\n")


if __name__ == "__main__":
    main()
