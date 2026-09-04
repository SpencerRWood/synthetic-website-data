# syntax=docker/dockerfile:1
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SYNTHETIC_WEBSITE_DATA_CONFIG=/app/configs/default.yaml \
    SYNTHETIC_WEBSITE_DATA_OUTPUT_DIR=/data

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install the project so the image exposes the same CLI as a local installation.
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

# These files are needed only when `generate --load` or `generate-and-load` runs.
COPY alembic.ini ./
COPY alembic ./alembic
COPY configs ./configs

# Generated exports are intentionally written to a volume, not the image layer.
VOLUME ["/data"]

ENTRYPOINT ["synthetic-website-data"]
CMD ["generate"]
