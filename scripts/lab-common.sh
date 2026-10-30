#!/usr/bin/env bash
# Sourced by the lab commands. Every Kubernetes operation selects this lab explicitly.
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$LAB_ROOT"
export PATH="$LAB_ROOT/.tools/bin:$PATH"
export KUBECONFIG="$LAB_ROOT/.local/kubeconfig"
LAB_CONTEXT=kind-financial-showcase
LAB_NAMESPACE=showcase
k() { kubectl --kubeconfig "$KUBECONFIG" --context "$LAB_CONTEXT" "$@"; }
lab_require() {
  test -f "$KUBECONFIG" || { echo 'Run make lab-up first.' >&2; exit 1; }
  test "$(k config view --minify -o jsonpath='{.contexts[0].context.cluster}')" = "$LAB_CONTEXT"
}
