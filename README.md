# synthetic-website-data

Synthetic website event-stream data generator for local analytics and raw
PostgreSQL loading experiments.

The simulator generates visitors, sessions, page traversal, event types, and
event-specific properties from YAML configuration. The raw analytical source is
the event stream:

```text
event_id
visitor_id
session_id
timestamp
event_type
page
properties
```

Profile and commerce details are emitted inside `properties`; the project does
not create raw visitor, customer, demographic, or profile tables.

## Visitor Profile Lifecycle

Visitors begin anonymous. A lightweight profile is attached to each in-memory
visitor and persists for the lifetime of that visitor across sessions:

```text
visitor created
  -> anonymous
  -> signup
     -> first_name
     -> last_name
     -> email
  -> checkout/order
     -> phone
     -> population-weighted ZIP
     -> state derived from ZIP
     -> geographic area code
```

Enrichment is lazy. Names, emails, phones, ZIP codes, and states are generated
only when a lifecycle event would make them observable to the website.
Anonymous page views do not expose profile data. Signup events expose configured
identity fields. Purchase events expose configured checkout fields while
preserving existing commerce properties such as `order_id` and `order_value`.

Faker with the `en_US` locale generates synthetic first and last names. Email
addresses use the generated name and the reserved `example.com` domain. Phone
numbers use the sampled geographic area code and the fictitious `555-0100`
through `555-0199` range. Faker is seeded from `dataset.random_seed`, and the
profile enricher uses its own seeded random stream so identical configs and
seeds reproduce identical visitor enrichment.

## Geography

Checkout geography is population-weighted by ZIP-like Census ZIP Code
Tabulation Area records:

```text
US population distribution
  -> ZIP code sampled by population
  -> state from the same ZIP record
  -> area code from the same geography record
```

The default checked-in reference file is:

```text
configs/distributions/us_geography.csv
```

Expected columns:

```csv
zip_code,state,area_code,population
45202,OH,513,15279
```

The checked-in file contains 33,100 ZIP rows from ReadyAPIs'
`curated-us-zips` public CSV, keeping only `zip_code`, `state`, and
`population` from that source. ReadyAPIs publishes population from U.S. Census
ACS 5-year data and ZIP/state location fields from USPS/SimpleMaps. ZCTAs are
Census approximations of USPS ZIP Code service areas for statistical analysis,
so ZIP-level population should be treated as an analytical approximation rather
than address-level USPS delivery truth.

Area codes are derived by joining the ZIPs to the public GeoInfo Dataset's
United States NANPA rows by ZIP code and choosing the most common NPA for each
ZIP. When a ZIP has no direct NPA match, the file uses the most common NPA for
that state from the same GeoInfo data. The simulator stores only one primary
area code per ZIP row.

The loader validates that the file exists, required columns are present,
population weights are non-negative with at least one positive row, ZIP/state
values are populated, and area codes look like three-digit NANP area codes.
Weights are normalized implicitly during sampling:

```text
P(zip) = zip_population / total_population
```

Geography is descriptive only in this branch. State, ZIP, and area code do not
change arrival rates, return probability, page traversal, conversion
probability, product preferences, order values, campaign exposure, or any other
behavior.

## Configuration

The default configuration loads the website graph from `configs/website.yaml`,
event property specs from `configs/event_properties.yaml`, and visitor profile
settings from `configs/default.yaml`:

```yaml
visitor_profile:
  enabled: true
  signup:
    enabled: true
    enrichment_probability: 1.0
    fields:
      - first_name
      - last_name
      - email
  checkout:
    enabled: true
    enrichment_probability: 1.0
    fields:
      - first_name
      - last_name
      - email
      - phone
      - shipping_state
      - shipping_postal_code
  geography:
    enabled: true
    distribution_file: distributions/us_geography.csv
```

Supported profile fields are `first_name`, `last_name`, `email`, `phone`,
`shipping_state`, and `shipping_postal_code`. Unsupported fields such as age,
income, household size, gender, education, occupation, marital status,
ethnicity, or political affiliation are rejected rather than inferred.

`enrichment_probability` applies to the lifecycle event as a whole and must be
between `0` and `1`. Set `visitor_profile.enabled: false` to disable all profile
enrichment and profile event properties.

Campaign and acquisition fields such as `utm_source`, `utm_medium`,
`utm_campaign`, `channel`, `referrer`, `device_type`, attribution, adstock, and
carryover are intentionally out of scope.

## Generate Data

Install dependencies:

```sh
uv sync --frozen --group dev
```

Generate CSV and JSON files:

```sh
uv run python src/main.py configs/default.yaml data
```

Outputs:

```text
data/visitors.csv
data/sessions.csv
data/events.csv
data/dataset.json
data/events.json
```

`events.csv` serializes `properties` as compact JSON for database loading.
`dataset.json` and `events.json` preserve `properties` as JSON objects.

## PostgreSQL Raw Event Loading

Set `DATABASE_URL`, apply migrations, and load generated events:

```sh
export DATABASE_URL="postgresql://user:password@host:5432/database"
uv run alembic upgrade head
uv run python -m synthetic_website_data.database data/events.csv --replace
```

The loader validates the exact CSV header:

```text
event_id,visitor_id,session_id,page,timestamp,event_type,properties
```

`raw.events.properties` is JSONB, so visitor profile enrichment does not require
a new Alembic migration.

## Checks

Run the local quality gate:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
SKIP=no-commit-to-branch uv run pre-commit run --all-files
```
