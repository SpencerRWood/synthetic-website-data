import csv
import json
from pathlib import Path

import pytest

from main import generate_and_export, main


def test_generate_and_export_writes_data_files(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "data"
    config_path.write_text(
        """
dataset:
  start_date: "2026-01-01T09:00:00"
  end_date: "2026-01-01T10:00:00"
  timezone: "America/New_York"
  random_seed: 42
website:
  entry_page: home
  terminal_pages:
    - checkout
  graph:
    home:
      products: 1.0
    products:
      checkout: 1.0
    checkout: {}
arrivals:
  maximum_rate_per_hour: 20
  annual_growth_rate: 0.0
  hourly_intensity:
    0: 0.0
    1: 0.0
    2: 0.0
    3: 0.0
    4: 0.0
    5: 0.0
    6: 0.0
    7: 0.0
    8: 0.0
    9: 1.0
    10: 0.0
    11: 0.0
    12: 0.0
    13: 0.0
    14: 0.0
    15: 0.0
    16: 0.0
    17: 0.0
    18: 0.0
    19: 0.0
    20: 0.0
    21: 0.0
    22: 0.0
    23: 0.0
  weekday_intensity:
    monday: 1.0
    tuesday: 1.0
    wednesday: 1.0
    thursday: 1.0
    friday: 1.0
    saturday: 1.0
    sunday: 1.0
sessions:
  drop_off_probability: 0.0
  max_page_views: 30
page_views:
  delay:
    distribution: gamma
    shape: 2.0
    scale_seconds: 0.001
""",
        encoding="utf-8",
    )

    outputs = generate_and_export(config_path, output_dir)

    assert set(outputs) == {
        "visitors_csv",
        "sessions_csv",
        "events_csv",
        "dataset_json",
        "events_json",
    }
    assert all(path.is_file() for path in outputs.values())

    with outputs["events_csv"].open(encoding="utf-8", newline="") as file:
        events = list(csv.DictReader(file))
    assert events
    assert list(events[0]) == [
        "event_id",
        "visitor_id",
        "session_id",
        "page",
        "timestamp",
        "event_type",
        "properties",
    ]
    assert events[0]["event_type"] == "page_view"
    assert json.loads(events[0]["properties"]) == {}

    dataset = json.loads(outputs["dataset_json"].read_text(encoding="utf-8"))
    assert dataset
    assert "sessions" in dataset[0]
    assert "event_type" in dataset[0]["sessions"][0]["events"][0]
    assert dataset[0]["sessions"][0]["events"][0]["properties"] == {}

    events_json = json.loads(outputs["events_json"].read_text(encoding="utf-8"))
    assert events_json[0]["event_type"] == "page_view"
    assert events_json[0]["properties"] == {}


def test_main_uses_default_config_and_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text(
        """
dataset:
  start_date: "2026-01-01T09:00:00"
  end_date: "2026-01-01T10:00:00"
  timezone: "America/New_York"
  random_seed: 42
website:
  entry_page: home
  terminal_pages:
    - checkout
  graph:
    home:
      checkout: 1.0
    checkout: {}
arrivals:
  maximum_rate_per_hour: 5
  annual_growth_rate: 0.0
  hourly_intensity:
    0: 0.0
    1: 0.0
    2: 0.0
    3: 0.0
    4: 0.0
    5: 0.0
    6: 0.0
    7: 0.0
    8: 0.0
    9: 1.0
    10: 0.0
    11: 0.0
    12: 0.0
    13: 0.0
    14: 0.0
    15: 0.0
    16: 0.0
    17: 0.0
    18: 0.0
    19: 0.0
    20: 0.0
    21: 0.0
    22: 0.0
    23: 0.0
  weekday_intensity:
    monday: 1.0
    tuesday: 1.0
    wednesday: 1.0
    thursday: 1.0
    friday: 1.0
    saturday: 1.0
    sunday: 1.0
sessions:
  drop_off_probability: 0.0
  max_page_views: 30
page_views:
  delay:
    distribution: gamma
    shape: 2.0
    scale_seconds: 0.001
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    main([])

    assert (tmp_path / "data" / "events.csv").is_file()
