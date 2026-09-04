from pathlib import Path

import pytest

from synthetic_website_data import cli
from synthetic_website_data.generation import DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_DIR


def test_generate_uses_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "env-config.yaml"
    output_dir = tmp_path / "env-output"
    output_path = output_dir / "events.csv"
    monkeypatch.setenv(cli.CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv(cli.OUTPUT_DIR_ENV_VAR, str(output_dir))
    captured: dict[str, Path] = {}

    def generate(config: Path, output: Path) -> dict[str, Path]:
        captured["config"] = config
        captured["output"] = output
        return {"events_csv": output_path}

    monkeypatch.setattr(cli, "generate_and_export", generate)

    cli.main(["generate"])

    assert captured == {"config": config_path, "output": output_dir}
    assert capsys.readouterr().out == f"events_csv\t{output_path}\n"


def test_cli_arguments_override_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(cli.CONFIG_PATH_ENV_VAR, "from-env.yaml")
    monkeypatch.setenv(cli.OUTPUT_DIR_ENV_VAR, "from-env")
    captured: dict[str, Path] = {}

    def generate(config: Path, output: Path) -> dict[str, Path]:
        captured["config"] = config
        captured["output"] = output
        return {}

    monkeypatch.setattr(cli, "generate_and_export", generate)
    config_path = tmp_path / "from-args.yaml"
    output_dir = tmp_path / "from-args"

    cli.main(
        ["generate", "--config", str(config_path), "--output-dir", str(output_dir)]
    )

    assert captured == {"config": config_path, "output": output_dir}


@pytest.mark.parametrize(
    "command",
    [["generate", "--load"], ["generate-and-load"]],
)
def test_load_commands_run_generation_and_postgres_load(
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
) -> None:
    captured: dict[str, Path] = {}

    def generate_and_load(config: Path, output: Path) -> dict[str, Path]:
        captured["config"] = config
        captured["output"] = output
        return {}

    monkeypatch.setattr(cli, "run_generate_and_load", generate_and_load)

    cli.main(command)

    assert captured == {
        "config": DEFAULT_CONFIG_PATH,
        "output": DEFAULT_OUTPUT_DIR,
    }
