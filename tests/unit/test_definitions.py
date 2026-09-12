import subprocess
from pathlib import Path

import pytest
from dagster import DagsterEventType

from synthetic_website_data.dagster import definitions


def test_definitions_load_and_expose_full_rebuild_job() -> None:
    job = definitions.defs.resolve_job_def("full_synthetic_rebuild")

    assert job.description == "Full Synthetic Rebuild"
    assert set(job.graph.node_dict) == {"generate_synthetic_data", "build_dbt"}


def test_generator_failure_prevents_dbt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        raise subprocess.CalledProcessError(1, command, output="generator failed")

    monkeypatch.setattr(
        "synthetic_website_data.dagster.definitions.subprocess.run", run
    )
    monkeypatch.setenv(definitions.DBT_PROJECT_DIR_ENV_VAR, str(tmp_path))

    result = definitions.full_synthetic_rebuild.execute_in_process(raise_on_error=False)

    assert not result.success
    assert calls == [["synthetic-website-data", "generate", "--load"]]


def test_dbt_failure_propagates_after_generator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command == ["dbt", "build"]:
            raise subprocess.CalledProcessError(1, command, output="dbt failed")
        return subprocess.CompletedProcess(command, 0, stdout="generator complete")

    monkeypatch.setattr(
        "synthetic_website_data.dagster.definitions.subprocess.run", run
    )
    monkeypatch.setenv(definitions.DBT_PROJECT_DIR_ENV_VAR, str(tmp_path))

    result = definitions.full_synthetic_rebuild.execute_in_process(raise_on_error=False)

    assert not result.success
    assert calls == [
        ["synthetic-website-data", "generate", "--load"],
        ["dbt", "build"],
    ]
    assert any(
        event.event_type == DagsterEventType.STEP_FAILURE for event in result.all_events
    )
