"""Local setup must not rotate an existing database/API credential on repeat runs."""

import shutil
import stat
import subprocess
import sys
from pathlib import Path


def test_setup_preserves_secrets_and_private_container_configuration(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "local-env.py"
    shutil.copyfile(Path(__file__).resolve().parents[2] / "scripts/local-env.py", script)
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True)
    environment = tmp_path / ".local/dev.env"
    original = environment.read_bytes()
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True)
    assert environment.read_bytes() == original
    assert stat.S_IMODE(environment.stat().st_mode) == 0o600
    assert stat.S_IMODE(environment.parent.stat().st_mode) == 0o700
    values = dict(line.split("=", 1) for line in original.decode().splitlines())
    assert values["COMPOSE_DATABASE_URL"].endswith("@db:5432/showcase")
    assert values["DATABASE_URL"].endswith("@127.0.0.1:15491/showcase")
