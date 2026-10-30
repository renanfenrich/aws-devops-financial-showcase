#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools/bin:$PATH"
python3 scripts/local-env.py
uv run --frozen python scripts/jenkins-prepare.py
docker build -f ci/jenkins/controller.Dockerfile -t financial-showcase-jenkins-controller:local .local/jenkins
docker build -f ci/jenkins/agent.Dockerfile -t financial-showcase-jenkins-agent:local .
umask 077
python3 - <<'PY'
from pathlib import Path
import secrets
Path('.local/jenkins/controller.env').write_text('SHOWCASE_JENKINS_PASSWORD=' + secrets.token_hex(32) + '\n')
PY
set -a
source .local/dev.env
source .local/jenkins/controller.env
set +a
compose=(docker compose -f ci/jenkins/compose.yaml)
cleanup() {
  "${compose[@]}" down --volumes >/dev/null 2>&1 || true
}
trap cleanup EXIT
rm -f .local/jenkins/ready
"${compose[@]}" up -d --wait controller db
uv run --frozen python scripts/jenkins-test.py &
verifier=$!
for _ in $(seq 1 180); do
  [[ -f .local/jenkins/ready ]] && break
  kill -0 "$verifier" 2>/dev/null || { wait "$verifier"; exit 1; }
  sleep 2
done
[[ -f .local/jenkins/ready ]] || { kill "$verifier"; exit 1; }
set -a
source .local/jenkins/agent.env
set +a
"${compose[@]}" up -d agent
wait "$verifier"
