#!/usr/bin/env python3
"""Read-only local lab preflight. Never modifies host networking or other projects."""

import ipaddress
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    for binary in ("docker", "git", "make", "python3", "ip"):
        if not shutil.which(binary):
            failures.append(f"missing {binary}")
    disk_gib = shutil.disk_usage(ROOT).free / 2**30
    memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    available_gib = int(memory["MemAvailable"].split()[0]) / 2**20
    if disk_gib < 20:
        failures.append("at least 20 GiB free disk required; no automatic cleanup is performed")
    if available_gib < 10:
        failures.append("at least 10 GiB available RAM required; run heavy profiles sequentially")
    if shutil.which("docker"):
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            failures.append("Docker daemon unavailable")
    if shutil.which("ip"):
        result = subprocess.run(["ip", "-j", "route"], capture_output=True, text=True, check=False)
        for route in json.loads(result.stdout or "[]"):
            destination = route.get("dst", "default")
            if destination != "default":
                network = ipaddress.ip_network(destination)
                for cidr in ("10.244.0.0/16", "10.96.0.0/12"):
                    if network.overlaps(ipaddress.ip_network(cidr)):
                        failures.append(f"lab CIDR {cidr} overlaps an existing host route")
    print(
        json.dumps(
            {
                "disk_free_gib": round(disk_gib, 1),
                "memory_available_gib": round(available_gib, 1),
                "failures": failures,
            },
            indent=2,
        )
    )
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
