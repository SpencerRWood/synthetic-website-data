"""Database connection configuration."""

import os

import psycopg
from sqlalchemy.engine import URL, make_url

DATABASE_URL_ENV_VAR = "DATABASE_URL"


class DatabaseConfigurationError(RuntimeError):
    """Raised when database connection configuration is missing or invalid."""


def get_database_url() -> str:
    """Return the configured PostgreSQL database URL."""
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if database_url is None or not database_url.strip():
        raise DatabaseConfigurationError(
            f"{DATABASE_URL_ENV_VAR} must be set to load events into PostgreSQL."
        )

    try:
        parsed_url = make_url(database_url)
    except Exception as error:
        raise DatabaseConfigurationError(
            f"{DATABASE_URL_ENV_VAR} is not a valid database URL."
        ) from error

    if parsed_url.get_backend_name() not in {"postgresql", "postgres"}:
        raise DatabaseConfigurationError(
            f"{DATABASE_URL_ENV_VAR} must use a PostgreSQL URL."
        )

    return database_url


def get_sqlalchemy_url() -> URL:
    """Return the configured PostgreSQL database URL for SQLAlchemy/Alembic."""
    url = make_url(get_database_url())
    if url.drivername in {"postgresql", "postgres"}:
        return url.set(drivername="postgresql+psycopg")
    return url


def connect() -> psycopg.Connection[object]:
    """Open a psycopg connection using environment configuration."""
    return psycopg.connect(get_database_url())
