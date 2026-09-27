"""Start the MacBook code location with protected, narrowly scoped runtime secrets."""

import os
import socket
import stat
from pathlib import Path

from sqlalchemy.engine import make_url

INFRASTRUCTURE_HOST = "swood-server.local"


def load_env(path: Path, environment: dict[str, str]) -> None:
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600:
        raise RuntimeError(f"Runtime environment file must be a mode 0600 file: {path}")
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key.isidentifier() or not key.isupper() or not value:
            raise RuntimeError(f"Invalid runtime environment entry in {path}")
        environment[key] = value


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    dbt = repo.parent / "synthetic-website-dbt"
    secrets = Path.home() / ".config/wood/synthetic-dagster"
    environment = os.environ.copy()
    for name in ("dagster", "data", "dbt"):
        load_env(secrets / f"{name}.env", environment)

    dagster_postgres = make_url(environment["DAGSTER_POSTGRES_URL"])
    data_postgres = make_url(environment["DATABASE_URL"])
    if not dagster_postgres.host or not dagster_postgres.port:
        raise RuntimeError("DAGSTER_POSTGRES_URL must include a host and port")
    if not data_postgres.host or not data_postgres.port:
        raise RuntimeError("DATABASE_URL must include a host and port")

    # Resolve the infrastructure host at every start so DHCP changes do not
    # make the protected URL snapshots stale. IPv4 matches the published DB port.
    infrastructure_ip = socket.getaddrinfo(
        INFRASTRUCTURE_HOST, None, family=socket.AF_INET, type=socket.SOCK_STREAM
    )[0][4][0]
    environment["DAGSTER_POSTGRES_URL"] = dagster_postgres.set(
        host=infrastructure_ip
    ).render_as_string(hide_password=False)
    environment["DATABASE_URL"] = data_postgres.set(
        host=infrastructure_ip
    ).render_as_string(hide_password=False)

    environment.update(
        DAGSTER_HOME=str(Path.home() / ".dagster"),
        SYNTHETIC_WEBSITE_DBT_PROJECT_DIR=str(dbt),
        DBT_PROFILES_DIR=str(dbt),
        DAGSTER_POSTGRES_HOST=infrastructure_ip,
        DAGSTER_POSTGRES_PORT=str(dagster_postgres.port),
        DAGSTER_POSTGRES_DB="dagster",
        DAGSTER_POSTGRES_USER="dagster",
        DBT_HOST=infrastructure_ip,
        DBT_PORT=str(data_postgres.port),
        DBT_USER="dbt_editor",
        PATH=f"{repo / '.venv/bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
    )
    Path(environment["DAGSTER_HOME"]).mkdir(exist_ok=True)
    os.chdir(repo)
    os.execve(  # noqa: S606 -- replace the supervisor process with the fixed Dagster CLI
        repo / ".venv/bin/dagster",
        [
            "dagster",
            "api",
            "grpc",
            "-m",
            "synthetic_website_data.dagster.definitions",
            "--host",
            "0.0.0.0",  # noqa: S104 -- remote Dagster control plane connects over LAN
            "--port",
            "4000",
        ],
        environment,
    )


if __name__ == "__main__":
    main()
