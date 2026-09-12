"""CLI-first Dagster job for a full synthetic website rebuild."""

import os
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import dagster as dg

DBT_PROJECT_DIR_ENV_VAR = "SYNTHETIC_WEBSITE_DBT_PROJECT_DIR"
GENERATOR_CLI_ENV_VAR = "SYNTHETIC_WEBSITE_DATA_CLI"


def _dbt_project_dir() -> Path:
    """Return the configurable local checkout containing the dbt project."""
    return Path(os.environ.get(DBT_PROJECT_DIR_ENV_VAR, "../synthetic-website-dbt"))


def _run_command(
    context: dg.OpExecutionContext,
    command: Sequence[str],
    *,
    cwd: Path | None = None,
) -> None:
    """Run a command, recording combined output and propagating failures."""
    try:
        completed = subprocess.run(  # noqa: S603 -- fixed internal CLI commands
            list(command),
            check=True,
            cwd=cwd,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        if error.stdout:
            context.log.error(error.stdout.rstrip())
        raise

    if completed.stdout:
        context.log.info(completed.stdout.rstrip())


@dg.op(
    description="Generate data and replace the PostgreSQL raw tables.",
    out=dg.Out(dg.Nothing),
)
def generate_synthetic_data(
    context: dg.OpExecutionContext,
) -> Iterator[dg.Output[None]]:
    """Delegate generation and raw loading to the installed generator CLI."""
    generator_cli = os.environ.get(GENERATOR_CLI_ENV_VAR, "synthetic-website-data")
    _run_command(context, [generator_cli, "generate", "--load"])
    yield dg.Output(None)


@dg.op(
    description="Run dbt build in the configured synthetic-website-dbt checkout.",
    ins={"start_after_generation": dg.In(dg.Nothing)},
)
def build_dbt(context: dg.OpExecutionContext) -> None:
    """Delegate transformations and tests to the existing dbt CLI project."""
    project_dir = _dbt_project_dir()
    if not project_dir.is_dir():
        message = (
            f"dbt project directory does not exist: {project_dir}. Set "
            f"{DBT_PROJECT_DIR_ENV_VAR} to the synthetic-website-dbt checkout."
        )
        raise FileNotFoundError(message)
    _run_command(context, ["dbt", "build"], cwd=project_dir)


@dg.job(description="Full Synthetic Rebuild")
def full_synthetic_rebuild() -> None:
    """Generate/load raw data, then build the dbt project."""
    build_dbt(start_after_generation=generate_synthetic_data())


defs = dg.Definitions(jobs=[full_synthetic_rebuild])
