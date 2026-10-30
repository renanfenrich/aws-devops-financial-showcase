#!/usr/bin/env python3
"""Install checksum-pinned tools inside this checkout; no sudo or global writes."""

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import platform
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(item):
    name, spec = item
    destination = ROOT / ".tools" / "bin" / name
    stamp = ROOT / ".tools" / f"{name}.json"
    if destination.exists() and stamp.exists():
        old = json.loads(stamp.read_text())
        if (
            old.get("archive_sha256") == spec["sha256"]
            and old.get("binary_sha256")
            == hashlib.file_digest(destination.open("rb"), "sha256").hexdigest()
        ):
            return f"{name} {spec['version']}: verified"
    request = urllib.request.Request(
        spec["url"], headers={"User-Agent": "financial-showcase-bootstrap"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError(f"{name}: archive checksum mismatch")
    if spec["member"]:
        if spec["url"].endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                binary = archive.read(spec["member"])
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                member = archive.getmember(spec["member"])
                if not member.isfile():
                    raise ValueError(f"{name}: expected regular archive member")
                binary = archive.extractfile(member).read()
    else:
        binary = data
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    os.replace(temporary, destination)
    stamp.write_text(
        json.dumps(
            {"archive_sha256": spec["sha256"], "binary_sha256": hashlib.sha256(binary).hexdigest()}
        )
        + "\n"
    )
    return f"{name} {spec['version']}: installed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        parser.error("G1 toolchain supports Linux x86_64; other platforms are not yet verified")
    tools = json.loads((ROOT / "toolchain.lock.json").read_text())["tools"]
    selected = {name: tools[name] for name in args.only} if args.only else tools
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(install, selected.items()):
            print(result)


if __name__ == "__main__":
    main()
