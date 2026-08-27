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

## PostgreSQL Raw Event Loading

The generator remains independent of PostgreSQL: first generate `events.csv`,
then load that CSV into the target database when `DATABASE_URL` is available.
Database credentials belong in environment configuration, not YAML simulation
configuration.

Apply schema migrations:

```sh
export DATABASE_URL="postgresql://user:password@host:5432/database"
uv run alembic upgrade head
```

Create a future migration:

```sh
uv run alembic revision --autogenerate -m "description"
```

Generate CSV files:

```sh
uv run python src/main.py configs/default.yaml data
```

Load generated events with the development replace workflow:

```sh
uv run python -m synthetic_website_data.database data/events.csv --replace
```

Generate the dataset, apply migrations, delete old `raw.events` rows, and
reload the newly generated `events.csv` in one step:

```sh
set -a; source .env; uv run python -m synthetic_website_data.generate_and_load
```

The VS Code `Run main.py` task runs this same workflow. It requires a local
`.env` file with `DATABASE_URL` and intentionally replaces `raw.events` every
time it succeeds.

The loader validates that the CSV header is exactly:

```text
event_id,visitor_id,session_id,page,timestamp
```

It then streams the CSV through psycopg's PostgreSQL `COPY` API into
`raw.events`. With `--replace`, `TRUNCATE raw.events` and `COPY` run in one
transaction so a failed load rolls back instead of partially replacing the
previous dataset. Without `--replace`, the loader appends and lets the
`event_id` primary key reject duplicates.

Alembic creates only the raw event table:

```text
raw.events
  event_id UUID PRIMARY KEY
  visitor_id UUID NOT NULL
  session_id UUID NOT NULL
  page TEXT NOT NULL
  timestamp TIMESTAMPTZ NOT NULL
```

Indexes are intentionally limited to downstream analytics access patterns:
`visitor_id`, `(session_id, timestamp)`, and `timestamp`.

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
