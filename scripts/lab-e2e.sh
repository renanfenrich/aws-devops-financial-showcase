#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lab-common.sh"
lab_require
extra=()
if [[ "$(cat .local/platform-mode)" == argocd-published:* ]]; then
  extra+=(--gitops)
fi
uv run --frozen python scripts/e2e.py "${extra[@]}" "$@"
