# template-synthetic-data

A minimal, typed synthetic data generation template with `uv`, Ruff, mypy, pytest, pre-commit, GitHub Actions, and semantic-release wired together.

## Intended Use

Use this template for projects that generate synthetic datasets and scenario-based records. The repository infrastructure is ready
for local development and CI; the package modules are intentionally thin
placeholders for project-specific implementation.

## Project Layout

```text
src/template_synthetic_data/
  __init__.py
  py.typed
  config.py
  distributions.py
  generators.py
  models.py
  rates.py
  exporters/
    __init__.py
    csv.py
    json.py
    parquet.py
  scenarios/
    __init__.py
    example.py
tests/
  unit/
    test_template_integrity.py
  integration/
```

Keep reusable Python code under `src/template_synthetic_data/` and tests under `tests/`.
The `py.typed` marker declares the package as typed.

## Local Setup

Install dependencies into the local environment:

```sh
uv sync --frozen --group dev
```

Install pre-commit hooks:

```sh
uv run pre-commit install
```

Run all baseline checks locally:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv build
uv run pre-commit run --all-files
```

Use Ruff to apply safe fixes:

```sh
uv run ruff check --fix .
uv run ruff format .
```

## Linting, Formatting, And Typing

Ruff and mypy follow the same conventions as the Python library template:
Python 3.14, `src/` layout, strict mypy, 88-character line length, Ruff import
sorting, and normal `assert` statements allowed in tests.

## Tests

The initial tests verify template integrity without pretending application
behavior exists. Add focused unit and integration tests alongside each real
implementation as the copied project grows.

## Build And Release

The package builds with Hatchling through `uv build`. GitHub Actions validate
Ruff, formatting, mypy, pytest, pre-commit, and package builds. The release
workflow uses python-semantic-release with conventional commits and tags like
`v0.0.1`.

## Copy And Rename

After copying this template, replace these names everywhere:

- project name: `template-synthetic-data`
- package name: `template_synthetic_data`


Then update package metadata in `pyproject.toml`, refresh `uv.lock` with
`uv lock`, run `uv sync --frozen --group dev`, and run the baseline checks.
