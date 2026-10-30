#!/usr/bin/env python3
"""Create local-only synthetic credentials without printing them."""

import os
import secrets
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
directory = root / ".local"
directory.mkdir(mode=0o700, exist_ok=True)
directory.chmod(0o700)
path = directory / "dev.env"
if not path.exists():
    password = secrets.token_hex(24)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(
            f"POSTGRES_PASSWORD={password}\nPOSTGRES_ADMIN_PASSWORD={secrets.token_hex(32)}\nAPI_TOKEN={secrets.token_hex(32)}\nDATABASE_URL=postgresql://app:{password}@127.0.0.1:15491/showcase\n"
        )
values = dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
if "COMPOSE_DATABASE_URL" not in values:
    # Keep the complete container DSN private, and preserve existing credentials.
    password = quote(values["POSTGRES_PASSWORD"], safe="")
    with path.open("a") as stream:
        stream.write(f"COMPOSE_DATABASE_URL=postgresql://app:{password}@db:5432/showcase\n")
path.chmod(0o600)
print("Local environment ready in .local/dev.env (not displayed)")
