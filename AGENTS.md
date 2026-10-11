# Repository Guidance

## Purpose and boundaries
- Generate typed synthetic visitor, session, and event data; downstream dbt models and analysis live in sibling repos.
- Preserve deterministic generation and the raw-event contract consumed by loaders and dbt.

## Development
- Keep generation logic in `src/`, configs in `configs/`, and Alembic migrations under `alembic/`.
- Use the documented CLI and `scripts/dev` for local commands that need resolved runtime configuration.

## Validation
- Run `uv sync --frozen --group dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`, and `uv run pre-commit run --all-files`.
- Validate database changes with the Alembic commands documented in `README.md`.

## Architecture constraints
- Keep source loading and schema evolution separate from dbt's analytical transformations.
- Do not add an implicit orchestration schedule to the documented Dagster integration.

## Safety
- Keep database credentials and generated local data outside Git.

## Branching strategy

- This repository uses **release-branch integration**. Create Story branches from the verified active `release/vX.Y.Z` and target Story PRs there; `main` changes only after the release readiness gate.
- Follow the [canonical branching and delivery policy](https://github.com/SpencerRWood/codex-config/blob/main/docs/branching-policy.md), available through the installed codex-config source path. Verify the strategy, release association, fetched base and PR target before implementation and record them in Story evidence. Story completion does not authorize publication or deployment; retain existing review, CI, security and rollback requirements.
