# synthetic-website-data

Typed synthetic website event-stream data generation with configurable traffic,
session traversal, event properties, file exports, and PostgreSQL raw event
loading.

## Intended Use

Use this project to generate deterministic synthetic website analytics data for
local development, demos, and downstream warehouse or dbt workflows.

## Project Layout

```text
src/synthetic_website_data/
  __init__.py
  py.typed
  config.py
  generators.py
  models.py
  exporters/
    __init__.py
    csv.py
    json.py
  scenarios/
    __init__.py
    example.py
tests/
  unit/
    test_template_integrity.py
  integration/
```

Keep reusable Python code under `src/synthetic_website_data/` and tests under `tests/`.
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
synthetic-website-data generate
```

The installed CLI is entirely non-interactive. Set paths with flags or
environment variables (flags take precedence):

```sh
export SYNTHETIC_WEBSITE_DATA_CONFIG=configs/default.yaml
export SYNTHETIC_WEBSITE_DATA_OUTPUT_DIR=data
synthetic-website-data generate --config configs/demo.yaml --output-dir demo-data
```

The default simulation config keeps rates and behavior in `configs/default.yaml`
and loads website pages plus the navigation graph from `configs/website.yaml`
through `website.graph_path`. It also loads event property generation settings
from `configs/event_properties.yaml` through `event_properties_path`.

Pages map to event types in `configs/website.yaml`:

```yaml
pages:
  product_detail:
    event_type: product_view
  cart:
    event_type: add_to_cart
  order_confirmation:
    event_type: purchase
```

Event properties can be configured per event type:

```yaml
event_properties:
  add_to_cart:
    product_id:
      type: id
      prefix: sku_
      min: 1000
      max: 9999
    quantity:
      type: integer
      min: 1
      max: 4
    price:
      type: float
      min: 12.0
      max: 240.0
      decimals: 2
    source_label: configured literal value
```

Supported property spec types are `choice`, `integer`, `float`, `id`, and
`literal`. Plain scalar YAML values are treated as literals.

Load generated events with the development replace workflow:

```sh
uv run python -m synthetic_website_data.database data/events.csv --replace
```

Generate the dataset, apply migrations, delete old raw rows, and reload the
newly generated `events.csv`, `campaigns.csv`, and `website.csv` in one step:

```sh
export DATABASE_URL="postgresql://user:password@host:5432/database"
synthetic-website-data generate --load
```

`synthetic-website-data generate-and-load` is an equivalent explicit command.
Both loading commands require `DATABASE_URL`; they do not read credentials from
YAML or prompt for them.

The VS Code `Generate and load PostgreSQL` task runs this same workflow. It
requires a local `.env` file with `DATABASE_URL` and intentionally replaces
`raw.events`,
`raw.campaigns`, and `raw.website` every time it succeeds. `raw.website` is a
directed adjacency list of the configured site graph:

```text
from_page,to_page,transition_probability
home,products,0.5
products,cart,0.3
```

Use it as a dbt source for the expected navigation graph, and derive observed
session-to-session transitions from `raw.events` for a Sankey or funnel model.

The loader validates that the CSV header is exactly:

```text
event_id,visitor_id,session_id,page,timestamp,event_type,properties
```

It then streams the CSV through psycopg's PostgreSQL `COPY` API into
`raw.events`. With `--replace`, `TRUNCATE raw.events` and `COPY` run in one
transaction so a failed load rolls back instead of partially replacing the
previous dataset. Without `--replace`, the loader appends and lets the
`event_id` primary key reject duplicates.

Alembic creates raw source tables including:

```text
raw.events
  event_id UUID PRIMARY KEY
  visitor_id UUID NOT NULL
  session_id UUID NOT NULL
  page TEXT NOT NULL
  timestamp TIMESTAMPTZ NOT NULL
  event_type TEXT NOT NULL
  properties JSONB NOT NULL
```

```text
raw.website
  from_page TEXT NOT NULL
  to_page TEXT NOT NULL
  transition_probability NUMERIC NOT NULL
  PRIMARY KEY (from_page, to_page)
```

Indexes are intentionally limited to downstream analytics access patterns:
`visitor_id`, `(session_id, timestamp)`, and `timestamp`.

## Linting, Formatting, And Typing

Ruff and mypy follow the same conventions as the Python library baseline:
Python 3.14, `src/` layout, strict mypy, 88-character line length, Ruff import
sorting, and normal `assert` statements allowed in tests.

## Tests

Tests cover configuration validation, traffic arrival simulation, website
traversal, event generation, file export, and PostgreSQL loader validation.

## Build And Release

The package builds with Hatchling through `uv build`. The release workflow
validates mypy, pytest, and pre-commit before python-semantic-release runs with
conventional commits and tags like `v0.5.0`. Ruff linting and formatting run
through pre-commit.
