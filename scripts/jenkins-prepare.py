#!/usr/bin/env python3
"""Fetch the pinned plugin closure and snapshot the committed checkout only."""

import base64
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / ".local/jenkins"


def plugin(spec):
    destination = DESTINATION / "plugins" / (spec["name"] + ".jpi")
    expected = base64.b64decode(spec["sha256"]).hex()
    if (
        destination.exists()
        and hashlib.file_digest(destination.open("rb"), "sha256").hexdigest() == expected
    ):
        return
    data = urlopen(spec["url"], timeout=120).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Plugin checksum mismatch: {spec['name']}")
    destination.write_bytes(data)


def main():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise SystemExit(
            "Commit the intended snapshot before running Jenkins; no dirty SHA evidence"
        )
    DESTINATION.mkdir(mode=0o700, parents=True, exist_ok=True)
    (DESTINATION / "plugins").mkdir(exist_ok=True)
    snapshot = DESTINATION / "snapshot"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    snapshot.mkdir(exist_ok=True)
    # Snapshot contains tracked files only, never .local credentials or tool caches.
    archive_data = subprocess.check_output(["git", "archive", sha], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive_data)) as archive:
        archive.extractall(snapshot, filter="data")
    (snapshot / ".source-sha").write_text(sha + "\n")
    shutil.copyfile(snapshot / "ci/jenkins/init.groovy", DESTINATION / "init.groovy")
    lock = json.loads((ROOT / "ci/jenkins/plugins.lock.json").read_text())
    expected_plugins = {spec["name"] + ".jpi" for spec in lock["plugins"]}
    for path in (DESTINATION / "plugins").glob("*.jpi"):
        if path.name not in expected_plugins:
            path.unlink()
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(plugin, lock["plugins"]))
    print(f"Jenkins snapshot and {len(lock['plugins'])} verified plugins prepared for {sha}")


if __name__ == "__main__":
    main()
