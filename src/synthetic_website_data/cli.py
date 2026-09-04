"""Non-interactive command-line interface for synthetic website data."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from synthetic_website_data.generate_and_load import run_generate_and_load
from synthetic_website_data.generation import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    generate_and_export,
)

CONFIG_PATH_ENV_VAR = "SYNTHETIC_WEBSITE_DATA_CONFIG"
OUTPUT_DIR_ENV_VAR = "SYNTHETIC_WEBSITE_DATA_OUTPUT_DIR"


def _default_path(environment_variable: str, default: Path) -> Path:
    """Return an environment-configured path, falling back to the project default."""
    return Path(os.environ.get(environment_variable, default))


def _add_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_path(CONFIG_PATH_ENV_VAR, DEFAULT_CONFIG_PATH),
        help=(
            "YAML simulation config "
            f"(default: ${CONFIG_PATH_ENV_VAR} or {DEFAULT_CONFIG_PATH})"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_path(OUTPUT_DIR_ENV_VAR, DEFAULT_OUTPUT_DIR),
        help=(
            "directory for generated files "
            f"(default: ${OUTPUT_DIR_ENV_VAR} or {DEFAULT_OUTPUT_DIR})"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without reading stdin or prompting the user."""
    parser = argparse.ArgumentParser(prog="synthetic-website-data")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="generate dataset export files")
    _add_generation_options(generate)
    generate.add_argument(
        "--load",
        action="store_true",
        help="apply migrations and replace PostgreSQL raw tables after generation",
    )

    generate_and_load = commands.add_parser(
        "generate-and-load",
        help="generate files, apply migrations, and load PostgreSQL raw tables",
    )
    _add_generation_options(generate_and_load)
    return parser


def _write_outputs(outputs: dict[str, Path]) -> None:
    for label, path in outputs.items():
        sys.stdout.write(f"{label}\t{path}\n")


def main(argv: Sequence[str] | None = None) -> None:
    """Run a generation command using only arguments and environment variables."""
    args = build_parser().parse_args(argv)
    if args.command == "generate" and not args.load:
        _write_outputs(generate_and_export(args.config, args.output_dir))
        return

    run_generate_and_load(args.config, args.output_dir)
