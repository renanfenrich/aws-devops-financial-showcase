#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lab-common.sh"
kind delete cluster --name financial-showcase --kubeconfig "$KUBECONFIG"
rm -f .local/platform-mode .local/kubeconfig
echo 'Only the financial-showcase kind cluster was removed. Source and local credentials were preserved.'
