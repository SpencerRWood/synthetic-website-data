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

Sign in to the self-hosted Infisical instance with your developer account, then
run local commands through `./scripts/dev`. The launcher reads `DATABASE_URL`
from `Infrastructure Dev/dev:/synthetic-website-data`. Ordinary generation paths
use the application defaults or CLI flags. No local `.env` file is required.

```sh
infisical login --domain=https://dev-infisical.woodhost.cloud/api --method=user --interactive
./scripts/dev uv run --frozen synthetic-website-data generate --output-dir data
```

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

## Docker

Build an image containing the installed CLI:

```sh
docker build -t synthetic-website-data .
```

Generated files are written to `/data`, which is declared as a Docker volume so
they are never stored in the container's writable filesystem. Bind-mount a host
directory to retain the exports:

```sh
mkdir -p data
docker run --rm -v "$(pwd)/data:/data" synthetic-website-data
```

The image defaults to `synthetic-website-data generate`. Pass another CLI
command or options after the image name:

```sh
docker run --rm -v "$(pwd)/data:/data" synthetic-website-data \
  generate --config /app/configs/default.yaml --output-dir /data
```

For PostgreSQL loading, pass the Infisical-injected `DATABASE_URL` into the
container by variable name:

```sh
./scripts/dev docker run --rm \
  -e DATABASE_URL \
  -v "$(pwd)/data:/data" \
  synthetic-website-data generate-and-load
```

`DATABASE_URL` is required only by `generate --load` and
`generate-and-load`. You can override the packaged simulation configuration
and output mount with `SYNTHETIC_WEBSITE_DATA_CONFIG` and
`SYNTHETIC_WEBSITE_DATA_OUTPUT_DIR`, respectively.

## Dagster integration

This repository optionally exposes one Dagster gRPC code location. Its **Full
Synthetic Rebuild** job generates and loads synthetic data, then invokes the
sibling dbt project. It deliberately has no schedule or sensor, so it remains
safe to run directly from the CLI without a Dagster deployment.

```text
Full Synthetic Rebuild
  generate_synthetic_data  ->  build_dbt
  synthetic-website-data       dbt build
  generate --load              (synthetic-website-dbt)
```

The job is defined at `synthetic_website_data.dagster.definitions` and delegates
to the existing CLIs using argument arrays.
`SYNTHETIC_WEBSITE_DBT_PROJECT_DIR` identifies the local sibling dbt checkout;
the default (`../synthetic-website-dbt`) is relative to the data repository.

### Deployment model

A production deployment can run the Dagster webserver and daemon separately
from this gRPC code location. The code-location host requires this repository,
the sibling `synthetic-website-dbt` checkout, database connectivity, and the
`DAGSTER_POSTGRES_*` settings when remote runs use PostgreSQL-backed Dagster
metadata. The control-plane host must be able to reach the gRPC endpoint.

```text
Dagster control plane
  webserver + daemon + metadata storage
        | gRPC
        v
Remote code location
  synthetic-website-data -> synthetic-website-dbt
```

Remote runs include the control plane's Dagster `instance_ref`, which refers to
`dagster_postgres.DagsterPostgresStorage`. The code-location host must therefore install
`dagster-postgres==0.29.16` and inherit these central Dagster PostgreSQL
variables before it starts the gRPC process:

```text
DAGSTER_POSTGRES_HOST
DAGSTER_POSTGRES_PORT
DAGSTER_POSTGRES_DB
DAGSTER_POSTGRES_USER
DAGSTER_POSTGRES_PASSWORD
DAGSTER_POSTGRES_URL
```

`DAGSTER_POSTGRES_URL` is the storage setting serialized into the remote run's
instance reference. Its host must be reachable from the code-location host and
use a published port; do not use a container-only hostname. The component
variables in `.env.example` document the same connection without credentials.
For a local code-location process, use `./scripts/dev --dagster <existing command>`;
it also injects the shared `/dagster` and `/synthetic-website-dbt` secrets and
sets ordinary host, port, database, and user defaults.

Validate the code-location runtime and its route to Dagster PostgreSQL before
starting the gRPC process:

```sh
uv run python -c "import dagster_postgres; print('dagster-postgres OK')"
nc -zv "$DAGSTER_POSTGRES_HOST" "$DAGSTER_POSTGRES_PORT"
```

Configure a process supervisor, TLS, authentication, network policy, and
service discovery according to the environment that hosts the code location.
Verify the control plane can reach the gRPC endpoint before launching **Full
Synthetic Rebuild**.

The required environment variables are:

```text
DATABASE_URL
SYNTHETIC_WEBSITE_DATA_CONFIG (optional)
SYNTHETIC_WEBSITE_DATA_OUTPUT_DIR (optional)
SYNTHETIC_WEBSITE_DBT_PROJECT_DIR
DBT_HOST, DBT_PORT, DBT_USER, DBT_PASSWORD, DBT_DBNAME, DBT_SCHEMA, DBT_THREADS
DAGSTER_POSTGRES_HOST, DAGSTER_POSTGRES_PORT, DAGSTER_POSTGRES_DB
DAGSTER_POSTGRES_USER, DAGSTER_POSTGRES_PASSWORD, DAGSTER_POSTGRES_URL
```

## PostgreSQL Raw Event Loading

The generator remains independent of PostgreSQL: first generate `events.csv`,
then load that CSV into the target database when `DATABASE_URL` is available.
Database credentials belong in environment configuration, not YAML simulation
configuration.

Apply schema migrations:

```sh
./scripts/dev uv run --frozen alembic upgrade head
```

Create a future migration:

```sh
./scripts/dev uv run --frozen alembic revision --autogenerate -m "description"
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
./scripts/dev uv run --frozen python -m synthetic_website_data.database data/events.csv --replace
```

Generate the dataset, apply migrations, delete old raw rows, and reload the
newly generated `events.csv`, `campaigns.csv`, and `website.csv` in one step:

```sh
./scripts/dev uv run --frozen synthetic-website-data generate --load
```

`synthetic-website-data generate-and-load` is an equivalent explicit command.
Both loading commands require `DATABASE_URL`; they do not read credentials from
YAML or prompt for them.

The VS Code `Generate and load PostgreSQL` task runs this same workflow through
Infisical and intentionally replaces
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
