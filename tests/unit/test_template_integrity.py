import tomllib
from importlib import import_module
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_package_can_be_imported() -> None:
    package = import_module("synthetic_website_data")

    assert package.__all__ == ()


def test_project_metadata_describes_package() -> None:
    pyproject = load_pyproject()
    project = pyproject["project"]

    assert project["name"] == "synthetic-website-data"
    assert project["description"] == "Synthetic website event-stream data generator."
    assert project["requires-python"] == ">=3.14"
    assert project["dependencies"] == [
        "alembic>=1.17.2",
        "Faker>=38.2.0",
        "psycopg>=3.3.2",
        "PyYAML>=6.0.3",
        "SQLAlchemy>=2.0.45",
    ]


def test_project_declares_typed_src_package() -> None:
    pyproject = load_pyproject()
    project = pyproject["project"]
    tool = pyproject["tool"]
    hatch_targets = tool["hatch"]["build"]["targets"]

    assert (ROOT / "src" / "synthetic_website_data" / "py.typed").is_file()
    assert "Typing :: Typed" in project["classifiers"]
    assert hatch_targets["wheel"]["packages"] == [
        "src/synthetic_website_data",
    ]
    assert tool["coverage"]["run"]["source"] == ["synthetic_website_data"]
