#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lab-common.sh"
mkdir -p artifacts/platform
helm lint platform/chart
helm template financial-showcase platform/chart --namespace showcase --kube-version 1.36.4 > artifacts/platform/rendered.yaml
promtool test rules platform/alerts.test.yml
python3 - <<'PY'
import json
from pathlib import Path
p=Path('platform/chart/dashboards/operations.json')
d=json.loads(p.read_text())
assert d['uid']=='financial-operations' and len(d['panels'])==4
assert d['editable'] is False
for p in Path('platform/chart/templates').glob('*.yaml'):
    assert 'kind:' in p.read_text(), p
print('Platform templates, dashboard and alert contract passed.')
PY
