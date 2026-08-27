from pathlib import Path
from random import Random

import pytest

from synthetic_website_data.config import ConfigurationError
from synthetic_website_data.distributions import (
    load_geography_distribution,
    sample_normal,
    sample_weighted_category,
)

ROOT = Path(__file__).resolve().parents[2]


def test_sample_weighted_category_favors_larger_weights() -> None:
    rng = Random(42)  # noqa: S311
    samples = [
        sample_weighted_category({"large": 900, "small": 100}, rng) for _ in range(1000)
    ]

    assert samples.count("large") > 800


def test_sample_normal_uses_provided_rng() -> None:
    first = sample_normal(10.0, 2.0, Random(42))  # noqa: S311
    second = sample_normal(10.0, 2.0, Random(42))  # noqa: S311

    assert first == second


def test_load_geography_distribution_samples_configured_zip(tmp_path: Path) -> None:
    path = tmp_path / "us_geography.csv"
    path.write_text(
        "zip_code,state,area_code,population\n45202,OH,513,100\n10001,NY,212,900\n",
        encoding="utf-8",
    )
    distribution = load_geography_distribution(path)

    sample = distribution.sample(Random(1))  # noqa: S311

    assert sample in distribution.records
    assert {record.zip_code for record in distribution.records} == {"45202", "10001"}


def test_load_geography_distribution_rejects_malformed_data(tmp_path: Path) -> None:
    path = tmp_path / "us_geography.csv"
    path.write_text(
        "zip_code,state,area_code,population\n45202,OH,513,-1\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="population"):
        load_geography_distribution(path)


def test_checked_in_geography_distribution_contains_all_source_zip_rows() -> None:
    distribution = load_geography_distribution(
        ROOT / "configs" / "distributions" / "us_geography.csv"
    )

    assert len(distribution.records) == 33100
    assert sum(distribution.weights) > 300_000_000
    assert all(record.area_code.isdigit() for record in distribution.records)
