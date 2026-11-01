#!/usr/bin/env python3
"""Rehearse native Terraform state recovery using disposable synthetic local state only."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rehearse(terraform, expected_version, checks):
    def require(condition, name):
        if not condition:
            raise RuntimeError("Recovery check failed")
        checks[name] = True

    previous_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="showcase-state-recovery-") as temporary:
            workspace = Path(temporary)
            home, source, restored = [workspace / name for name in ("home", "source", "restored")]
            for directory in (home, source, restored):
                directory.mkdir(mode=0o700)
            config = home / "terraform.rc"
            config.write_text("")
            # No workstation CLI flags, logs, workspace, backend cache or credentials.
            environment = {
                "HOME": str(home),
                "TF_CLI_CONFIG_FILE": str(config),
                "CHECKPOINT_DISABLE": "1",
                "TF_IN_AUTOMATION": "true",
                "TF_INPUT": "false",
            }

            def invoke(directory, *arguments):
                return subprocess.run(
                    [str(terraform), *arguments],
                    cwd=directory,
                    env=environment,
                    capture_output=True,
                    check=False,
                    timeout=20,
                )

            def successful(directory, *arguments):
                result = invoke(directory, *arguments)
                if result.returncode:
                    # Native errors can contain state values; never publish their text.
                    raise RuntimeError("Local Terraform command failed")
                return result.stdout

            version = json.loads(successful(home, "version", "-json"))["terraform_version"]
            require(version == expected_version, "pinned_terraform")
            fixture = {
                "version": 4,
                "terraform_version": version,
                "serial": 5,
                "lineage": str(uuid.uuid4()),
                "outputs": {
                    "rehearsal": {
                        "value": "SYNTHETIC_STATE_VALUE_MUST_NOT_PUBLISH",
                        "type": "string",
                        "sensitive": True,
                    }
                },
                "resources": [],
            }
            original = source / "terraform.tfstate"
            original.write_text(json.dumps(fixture))
            original_bytes = original.read_bytes()
            backup = workspace / "backup.tfstate"
            backup.write_bytes(successful(source, "state", "pull"))
            exported = json.loads(backup.read_bytes())
            require(all(exported[key] == fixture[key] for key in fixture), "native_backup_export")
            checksum = hashlib.sha256(backup.read_bytes()).digest()

            def verified_push(candidate):
                if hashlib.sha256(candidate.read_bytes()).digest() != checksum:
                    raise ValueError("Backup checksum mismatch")
                successful(restored, "state", "push", str(candidate))

            damaged = workspace / "damaged.tfstate"
            damaged.write_bytes(backup.read_bytes() + b"\n")
            try:
                verified_push(damaged)
            except ValueError:
                require(not (restored / "terraform.tfstate").exists(), "corruption_rejected")
            else:
                raise RuntimeError("Corrupt backup was accepted")

            verified_push(backup)
            recovered = restored / "terraform.tfstate"
            recovered_bytes = recovered.read_bytes()
            require(
                json.loads(successful(restored, "state", "pull")) == exported,
                "native_restore_matches_backup",
            )
            for name, changes, diagnostic in (
                (
                    "lineage",
                    {"lineage": str(uuid.uuid4())},
                    b"cannot import state with lineage",
                ),
                (
                    "serial",
                    {"serial": fixture["serial"] - 1},
                    b"cannot import state with serial",
                ),
            ):
                candidate = workspace / f"wrong-{name}.tfstate"
                candidate.write_text(json.dumps({**exported, **changes}))
                result = invoke(restored, "state", "push", str(candidate))
                require(
                    result.returncode != 0 and diagnostic in result.stderr.lower(),
                    f"native_{name}_guard",
                )
                require(
                    recovered.read_bytes() == recovered_bytes, f"{name}_refusal_preserves_state"
                )
            require(original.read_bytes() == original_bytes, "source_unchanged")
            require(hashlib.sha256(backup.read_bytes()).digest() == checksum, "backup_unchanged")
            require(
                all(
                    stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)
                    and not path.is_symlink()
                    for path in (workspace, *workspace.rglob("*"))
                ),
                "private_permissions",
            )
        require(not workspace.exists(), "temporary_state_removed")
    finally:
        os.umask(previous_umask)


def main():
    record = {
        "schema_version": 1,
        "mode": "synthetic-local-state",
        "checks": {},
        "passed": False,
        "boundaries": {
            "real_state_read": False,
            "remote_backend": False,
            "aws_verified": False,
            "encrypted_custody_verified": False,
        },
    }
    try:
        lock = json.loads((ROOT / "toolchain.lock.json").read_text())
        record["terraform_version"] = lock["tools"]["terraform"]["version"]
        terraform = shutil.which("terraform")
        if terraform is None:
            raise RuntimeError("Run make bootstrap first")
        rehearse(Path(terraform).resolve(), record["terraform_version"], record["checks"])
        record["passed"] = True
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        subprocess.TimeoutExpired,
        KeyboardInterrupt,
    ):
        record["error"] = "Synthetic recovery drill failed; no raw state or CLI output published"
    output = ROOT / "artifacts/state-recovery"
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("This synthetic drill accepts no arguments or real state paths")
    raise SystemExit(main())
