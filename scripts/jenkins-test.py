#!/usr/bin/env python3
"""Exercise a real isolated Jenkins pipeline and retain only non-secret evidence."""

import base64
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:18091"


def main():
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    authorization = (
        "Basic "
        + base64.b64encode(
            ("showcase-admin:" + os.environ["SHOWCASE_JENKINS_PASSWORD"]).encode()
        ).decode()
    )

    def request(path, data=None, headers=None):
        request_headers = {"Authorization": authorization, **(headers or {})}
        with opener.open(
            urllib.request.Request(BASE + path, data=data, headers=request_headers), timeout=20
        ) as response:
            return response.read()

    for _ in range(180):
        try:
            request("/api/json")
            break
        except urllib.error.URLError, OSError:
            time.sleep(2)
    else:
        raise SystemExit("Jenkins did not become ready; inspect its local container logs")
    descriptor = ET.fromstring(request("/computer/showcase-agent/jenkins-agent.jnlp"))
    secret = descriptor.find(".//argument").text
    env_path = ROOT / ".local/jenkins/agent.env"
    with open(env_path, "w", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
        stream.write("JENKINS_SECRET=" + secret + "\n")
    print("Jenkins controller ready; inbound agent secret stored locally, not displayed")
    # The shell orchestrator starts the agent after this point.
    (ROOT / ".local/jenkins/ready").touch()
    for _ in range(180):
        state = json.loads(request("/computer/showcase-agent/api/json"))
        if not state["offline"]:
            break
        time.sleep(2)
    else:
        raise SystemExit("Jenkins isolated agent did not connect")
    crumb = json.loads(request("/crumbIssuer/api/json"))
    number = json.loads(request("/job/g1/api/json"))["nextBuildNumber"]
    request("/job/g1/build?delay=0sec", b"", {crumb["crumbRequestField"]: crumb["crumb"]})
    build = None
    for _ in range(600):
        try:
            build = json.loads(request(f"/job/g1/{number}/api/json"))
            if not build["building"]:
                break
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
        time.sleep(2)
    if not build or build["building"]:
        raise SystemExit("Jenkins build exceeded the bounded smoke timeout")
    sha = request(f"/job/g1/{number}/artifact/source-sha.txt").decode().strip()
    expected_sha = (ROOT / ".local/jenkins/snapshot/.source-sha").read_text().strip()
    result = {
        "schema_version": 1,
        "source_sha": sha,
        "result": build["result"],
        "build_number": number,
        "duration_ms": build["duration"],
        "verified_at": datetime.now(UTC).isoformat(),
        "controller_executors": 0,
        "isolated_agent": True,
        "aws_credentials": False,
    }
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "jenkins.json").write_text(json.dumps(result, indent=2) + "\n")
    if build["result"] != "SUCCESS" or sha != expected_sha:
        # Console can contain failure stack traces. Keep it private, outside published artifacts.
        (ROOT / ".local/jenkins/console.log").write_bytes(request(f"/job/g1/{number}/consoleText"))
        raise SystemExit(f"Jenkins result {build['result']}; inspect .local/jenkins/console.log")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
