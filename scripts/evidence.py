#!/usr/bin/env python3
"""Capture source-bound gate results and retain immutable per-run evidence."""

import argparse
import contextlib
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "core": "verify",
    "infra": "infra-test",
    "atlantis": "atlantis-test",
    "e2e": "e2e",
    "jenkins": "jenkins-test",
    "security": "security",
}


def source_entry(root, name):
    """Hash a regular file or link target; never follow even an ancestor symlink."""
    parts = Path(name).parts
    if not parts or Path(name).is_absolute() or ".." in parts:
        raise ValueError("Git returned a path outside the checkout")
    entry = {"path": name}
    with contextlib.ExitStack() as cleanup:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        cleanup.callback(os.close, directory)
        try:
            for index, part in enumerate(parts[:-1]):
                info = os.stat(part, dir_fd=directory, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    return {
                        **entry,
                        "type": "blocked-by-link",
                        "ancestor": str(Path(*parts[: index + 1])),
                        "target": os.readlink(part, dir_fd=directory),
                    }
                directory = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                cleanup.callback(os.close, directory)
            info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                return {
                    **entry,
                    "type": "symlink",
                    "target": os.readlink(parts[-1], dir_fd=directory),
                }
            if not stat.S_ISREG(info.st_mode):
                return {**entry, "type": "non-regular", "mode": info.st_mode}
            descriptor = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("Source changed to a non-regular file during hashing")
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            return {**entry, "type": "file", "mode": stat.S_IMODE(info.st_mode), "sha256": digest}
        except FileNotFoundError:
            return {**entry, "type": "missing"}


def source_snapshot(root):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    entries = [source_entry(root, os.fsdecode(name)) for name in sorted(set(names)) if name]
    serialized = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha": git("rev-parse", "HEAD").decode().strip(),
        "dirty_worktree": bool(git("status", "--porcelain")),
        "source_tree_sha256": hashlib.sha256(serialized).hexdigest(),
    }


def fresh_reports(root, started):
    for path in sorted((root / "artifacts").rglob("*")):
        relative = path.relative_to(root / "artifacts")
        if (
            "history" in relative.parts
            or "e2e-history" in relative.parts
            or path.name.startswith("evidence-")
            or path.is_symlink()
            or path.suffix not in (".json", ".xml")
            or not path.is_file()
            or path.stat().st_mtime_ns < int(started.timestamp() * 1_000_000_000)
        ):
            continue
        if any(parent.is_symlink() for parent in path.parents if parent != root):
            continue
        content = path.read_bytes()
        if path.suffix == ".json":
            json.loads(content)
        else:
            ET.fromstring(content)
        yield path, content


def capture(root, gate, runner=None):
    target = TARGETS[gate]
    initial = source_snapshot(root)
    toolchain = json.loads((root / "toolchain.lock.json").read_text())
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:12]
    history = root / "artifacts/history" / run_id
    history.mkdir(parents=True)
    completed = (runner or subprocess.run)(["make", target], cwd=root, check=False)
    ended = datetime.now(UTC)
    final = source_snapshot(root)
    changed = (
        initial["sha"] != final["sha"]
        or initial["source_tree_sha256"] != final["source_tree_sha256"]
    )
    result = "inconclusive" if changed else "passed" if completed.returncode == 0 else "failed"
    effective_exit = completed.returncode if completed.returncode else int(changed)
    reports = {}
    for path, content in fresh_reports(root, started):
        relative = path.relative_to(root)
        destination = history / "reports" / relative.relative_to("artifacts")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        reports[str(relative)] = hashlib.sha256(content).hexdigest()
    record = {
        "schema_version": 2,
        "run_id": run_id,
        "sha": initial["sha"],
        "dirty_worktree": initial["dirty_worktree"],
        "source_tree_sha256": initial["source_tree_sha256"],
        "source_start": initial,
        "source_end": final,
        "source_changed_during_run": changed,
        "gate": gate,
        "command": f"make {target}",
        "started_at": started.isoformat(),
        "finished_at": ended.isoformat(),
        "command_exit_code": completed.returncode,
        "exit_code": effective_exit,
        "result": result,
        "toolchain": toolchain,
        "report_sha256": reports,
        "history_path": str(history.relative_to(root)),
        "boundaries": {
            "aws_provisioned": False,
            "atlantis_pr_e2e": "pending",
            "bitbucket_saas": "pending",
            "human_approval": "pending",
        },
    }
    content = json.dumps(record, indent=2) + "\n"
    (history / "evidence.json").write_text(content)
    latest = root / "artifacts" / f"evidence-{gate}.json"
    temporary = latest.with_name(f".evidence-{gate}-{run_id}.tmp")
    temporary.write_text(content)
    temporary.replace(latest)
    print(f"Evidence: {latest.relative_to(root)} ({result}; run {run_id})")
    return effective_exit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", default="core", choices=TARGETS)
    return capture(ROOT, parser.parse_args().gate)


if __name__ == "__main__":
    sys.exit(main())
