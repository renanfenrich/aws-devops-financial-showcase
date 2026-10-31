"""Run immutable SQL migrations once under a PostgreSQL transaction advisory lock."""

import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
LOCK_ID = 24910001


def migrate(database_url: str, directory: Path = MIGRATIONS) -> int:
    applied = 0
    with psycopg.connect(
        database_url, connect_timeout=5, options="-c statement_timeout=30000 -c lock_timeout=15000"
    ) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version text PRIMARY KEY, checksum text NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        files = sorted(directory.glob("*.sql"))
        if not files:
            raise RuntimeError("No migration files found")
        for path in files:
            content = path.read_bytes()
            checksum = hashlib.sha256(content).hexdigest()
            row = conn.execute(
                "SELECT checksum FROM schema_migrations WHERE version = %s", (path.name,)
            ).fetchone()
            if row:
                if row[0] != checksum:
                    raise RuntimeError("Applied migration checksum changed")
                continue
            conn.execute(content.decode())
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                (path.name, checksum),
            )
            applied += 1
    return applied


def main() -> None:
    try:
        count = migrate(os.environ["DATABASE_URL"])
    except KeyError, ValueError, RuntimeError, psycopg.Error:
        # Never print a connection URI or database exception that can include secrets.
        print(json.dumps({"level": "ERROR", "event": "migration_failed"}), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps({"level": "INFO", "event": "migrations_applied", "count": count}))


if __name__ == "__main__":
    main()
