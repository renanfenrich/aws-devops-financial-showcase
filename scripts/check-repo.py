#!/usr/bin/env python3
"""Small deterministic repository contracts shared by all CI adapters."""

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    failures = []
    lock = json.loads((root / "toolchain.lock.json").read_text())
    for name, tool in lock["tools"].items():
        if not re.fullmatch(r"[a-f0-9]{64}", tool["sha256"]):
            failures.append(f"{name}: invalid checksum")
        if urlparse(tool["url"]).scheme != "https":
            failures.append(f"{name}: expected HTTPS source")
    for path in (root / ".github/workflows").glob("*.yml"):
        text = path.read_text()
        workflow = yaml.safe_load(text)
        if "pull_request_target" in text:
            failures.append(f"{path.name}: untrusted privileged PR trigger")
        if workflow.get("permissions") != {"contents": "read"}:
            failures.append(f"{path.name}: top-level read-only permissions required")
        for action in re.findall(r"uses:\s*([^\s]+)", text):
            if not action.startswith("./") and not re.fullmatch(r"[\w./-]+@[a-f0-9]{40}", action):
                failures.append(f"{path.name}: action not SHA-pinned: {action}")
    for path in root.rglob("*.md"):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        for target in re.findall(r"\]\(([^\s)]+)", path.read_text()):
            if urlparse(target).scheme or target.startswith("#"):
                continue
            local = target.split("#")[0]
            if local and not (path.parent / local).exists():
                failures.append(f"{path.relative_to(root)}: broken local link {local}")
    for path in (root / "scripts").glob("*.sh"):
        result = subprocess.run(
            ["bash", "-n", str(path)], capture_output=True, text=True, check=False
        )
        if result.returncode:
            failures.append(f"{path.name}: shell syntax error")
    bitbucket = yaml.safe_load((root / "bitbucket-pipelines.yml").read_text())
    if not bitbucket.get("pipelines"):
        failures.append("Bitbucket pipelines missing")
    if failures:
        raise ValueError("\n".join(failures))
    print("Repository contracts passed")


if __name__ == "__main__":
    check()
