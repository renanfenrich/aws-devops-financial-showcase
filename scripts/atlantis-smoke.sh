#!/usr/bin/env bash
# Downloads are build-time only. Runtime has no Internet route, host mounts or credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
IMAGE=financial-showcase-atlantis:g1
RESOURCE="financial-showcase-atlantis-smoke-$$"
cleanup() {
  docker rm -f "$RESOURCE" >/dev/null 2>&1 || true
}
trap cleanup EXIT
[[ "$(uname -m)" == x86_64 ]] || { printf '%s\n' 'G1 Atlantis image supports Linux amd64.' >&2; exit 1; }
docker build --platform linux/amd64 --pull=false -t "$IMAGE" -f infra/atlantis/Dockerfile infra/atlantis
# No network interface except container loopback; no port is published.
docker run -d --name "$RESOURCE" --network none \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 512m --cpus 1 --pids-limit 128 \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --tmpfs /home/atlantis/.atlantis:rw,nosuid,nodev,uid=100,gid=1000,size=128m \
  "$IMAGE" >/dev/null
BASE=http://127.0.0.1:4141
ready=false
for _ in $(seq 1 60); do
  if docker exec "$RESOURCE" curl --fail --silent "$BASE/healthz" >/dev/null; then ready=true; break; fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$RESOURCE")" != true ]]; then break; fi
  sleep 1
done
if [[ "$ready" != true ]]; then docker logs "$RESOURCE"; exit 1; fi
docker exec "$RESOURCE" curl --fail --silent "$BASE/healthz" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'
docker exec "$RESOURCE" curl --fail --silent "$BASE/readyz" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'
docker exec "$RESOURCE" curl --fail --silent "$BASE/metrics" | python3 -c 'import re,sys; assert re.search(r"^# (HELP|TYPE) atlantis_", sys.stdin.read(), re.M)'
for route in plan apply; do
  [[ "$(docker exec "$RESOURCE" curl --silent --output /dev/null --write-out '%{http_code}' -X POST "$BASE/api/$route")" == 503 ]]
done
docker exec "$RESOURCE" atlantis version | python3 -c 'import sys; assert "v0.49.0" in sys.stdin.read()'
docker exec "$RESOURCE" terraform version -json | python3 -c 'import json,sys; assert json.load(sys.stdin)["terraform_version"] == "1.17.1"'
[[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$RESOURCE")" == none ]]
[[ "$(docker inspect -f '{{len .Mounts}}' "$RESOURCE")" == 0 ]]
[[ "$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$RESOURCE")" == true ]]
[[ "$(docker inspect -f '{{.Config.User}}' "$RESOURCE")" == atlantis ]]
AUTHZ=/usr/local/bin/showcase-atlantis-authz
[[ "$(docker exec -e USER_NAME=renanfenrich -e COMMAND_NAME=plan \
  -e BASE_REPO_OWNER=renanfenrich -e BASE_REPO_NAME=aws-devops-financial-showcase \
  "$RESOURCE" "$AUTHZ")" == pass ]]
for identity in renanfenrich octavariumdigitalpartners attacker; do
  DENIAL="$(docker exec -e USER_NAME="$identity" -e COMMAND_NAME=apply \
    -e BASE_REPO_OWNER=renanfenrich -e BASE_REPO_NAME=aws-devops-financial-showcase \
    "$RESOURCE" "$AUTHZ")"
  [[ "$DENIAL" != pass ]]
done
if docker exec "$RESOURCE" /usr/local/bin/showcase-deny-apply >/dev/null 2>&1; then
  printf '%s\n' 'Apply refusal unexpectedly succeeded.' >&2
  exit 1
fi
python3 -m unittest discover -s tests/infra -p 'test_*.py' -v
printf '%s\n' 'Atlantis offline smoke passed: startup, health/readiness, metrics, API disabled; GitHub PR/plan E2E PENDING.'
