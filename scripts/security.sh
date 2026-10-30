#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools/bin:$PATH"
export TRIVY_CACHE_DIR="$PWD/.cache/trivy"
umask 077
run_id="$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
raw="$PWD/.local/security/$run_id"
public="$PWD/artifacts/security/$run_id"
mkdir -p "$raw" "$public"
# Inspect once, then scan the immutable local content ID even if :local changes.
docker image inspect financial-showcase-api:local > "$raw/image-inspect.json"
image_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[0]["Id"])' "$raw/image-inspect.json")"
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]
fs_status=0
image_status=0
sbom_status=0
# Raw JSON and scanner stderr may include secret matches or source excerpts: stay private.
trivy fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL --exit-code 1 \
  --include-dev-deps --helm-kube-version 1.36.4 \
  --skip-dirs .local,.venv,.tools,.cache,.git,artifacts,infra/terragrunt/aws-foundation/.terragrunt-cache \
  --format json --output "$raw/filesystem.json" . > "$raw/filesystem.log" 2>&1 || fs_status=$?
trivy image --scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1 \
  --format json --output "$raw/image.json" "$image_id" > "$raw/image.log" 2>&1 || image_status=$?
trivy image --format spdx-json --output "$raw/sbom.spdx.json" "$image_id" \
  > "$raw/sbom.log" 2>&1 || sbom_status=$?
printf '{"filesystem":%s,"image":%s,"sbom":%s}\n' "$fs_status" "$image_status" "$sbom_status" > "$raw/status.json"
python3 scripts/security_report.py "$raw" "$public" "$run_id"
