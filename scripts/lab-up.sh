#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lab-common.sh"
mode="${1:-local}"
revision="${2:-$(git rev-parse HEAD)}"
[[ "$mode" == local || "$mode" == gitops ]] || { echo 'Usage: lab-up.sh [local|gitops] [published-40-character-SHA]' >&2; exit 2; }
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'A full source SHA is required.' >&2; exit 2; }
test -f .local/dev.env || { echo 'Run make local-env first.' >&2; exit 1; }
mkdir -p .local .cache/platform artifacts/platform
chmod 700 .local
python3 - "$mode" "$revision" <<'PY'
import json,subprocess,sys
from pathlib import Path
image=json.loads(subprocess.check_output(['docker','image','inspect','financial-showcase-api:local'],text=True))[0]
labels=image.get('Config',{}).get('Labels') or {}
provenance={'image_id':image['Id'],'source_revision':labels.get('org.opencontainers.image.revision'),
            'working_tree_dirty':labels.get('io.showcase.dirty')}
if sys.argv[1]=='gitops':
    if provenance['source_revision']!=sys.argv[2] or provenance['working_tree_dirty']!='false':
        raise SystemExit('GitOps requires make image from the clean, published source SHA. Local image provenance does not match.')
Path('.local/image-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
PY
python3 - <<'PY'
import ipaddress, json, os, secrets, shutil, subprocess
from pathlib import Path
routes=json.loads(subprocess.check_output(['ip','-j','route'],text=True))
for cidr in ('10.244.0.0/16','10.96.0.0/16'):
    net=ipaddress.ip_network(cidr)
    for route in routes:
        dest=route.get('dst','default')
        if dest!='default' and net.overlaps(ipaddress.ip_network(dest,strict=False)):
            raise SystemExit(f'Lab CIDR {cidr} conflicts with an existing route; stop before cluster creation.')
if shutil.disk_usage('.').free < 12*1024**3:
    raise SystemExit('Lab requires at least 12 GiB free disk space; no automatic cleanup is performed.')
env={}
for line in Path('.local/dev.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1); env[k]=v.strip().strip('"').strip("'")
for key in ('POSTGRES_PASSWORD','POSTGRES_ADMIN_PASSWORD','API_TOKEN'):
    if not env.get(key): raise SystemExit(f'Missing {key} in .local/dev.env')
grafana=Path('.local/grafana-password')
if not grafana.exists():
    grafana.write_text(secrets.token_hex(24)+'\n');grafana.chmod(0o600)
values={'POSTGRES_PASSWORD':env['POSTGRES_ADMIN_PASSWORD'],'APP_PASSWORD':env['POSTGRES_PASSWORD'],
        'DATABASE_URL':f"postgresql://app:{env['POSTGRES_PASSWORD']}@postgres:5432/showcase",'API_TOKEN':env['API_TOKEN'],
        'GRAFANA_PASSWORD':grafana.read_text().strip()}
path=Path('.local/k8s-secret.env'); path.write_text(''.join(f'{k}={v}\n' for k,v in values.items()));path.chmod(0o600)
PY
if ! kind get clusters 2>/dev/null | grep -qx financial-showcase; then
  kind create cluster --name financial-showcase --config platform/kind.yaml \
    --image kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed \
    --kubeconfig "$KUBECONFIG"
fi
lab_require
python3 - <<'PY'
import hashlib, urllib.request
from pathlib import Path
path=Path('.cache/platform/calico-v3.33.0.yaml')
url='https://raw.githubusercontent.com/projectcalico/calico/v3.33.0/manifests/calico.yaml'
if not path.exists(): path.write_bytes(urllib.request.urlopen(url,timeout=60).read())
raw=path.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='2de8f47595fb9c41b3f47d7b767a1f8e72ecf84057af834738ff12689a234da5','Calico source checksum mismatch'
text=raw.decode()
text=text.replace('name: CALICO_IPV4POOL_IPIP\n              value: "Always"','name: CALICO_IPV4POOL_IPIP\n              value: "Never"')
text=text.replace('name: CALICO_IPV4POOL_VXLAN\n              value: "Never"','name: CALICO_IPV4POOL_VXLAN\n              value: "Always"')
text=text.replace('# - name: CALICO_IPV4POOL_CIDR\n            #   value: "192.168.0.0/16"','- name: CALICO_IPV4POOL_CIDR\n              value: "10.244.0.0/16"')
for image,digest in {'node':'565d8db3200e443955557f8f28ff44ab8a4a456754bc74a19c4f2f3444af9b1c','calico':'4ebc20730127bc9e8bf1db5f5a2d8b58cf37fe0e891b3c7b5471992221d213e5','third-party-cni-plugins':'0f32f48279484c0d6f0e0d0e767b2d0e1a6c6ca34cb3421a61b989d992f3df41'}.items():
    text=text.replace(f'quay.io/calico/{image}:v3.33.0',f'quay.io/calico/{image}:v3.33.0@sha256:{digest}')
Path('.local/calico-rendered.yaml').write_text(text)
PY
k apply --server-side -f .local/calico-rendered.yaml >/dev/null
k -n kube-system rollout status daemonset/calico-node --timeout=300s
k wait --for=condition=Ready node --all --timeout=180s
k create namespace showcase --dry-run=client -o yaml | k apply -f - >/dev/null
k label namespace showcase pod-security.kubernetes.io/enforce=restricted pod-security.kubernetes.io/enforce-version=v1.36 --overwrite >/dev/null
k -n showcase create secret generic showcase-secrets --from-env-file=.local/k8s-secret.env --dry-run=client -o yaml | k apply -f - >/dev/null
kind load docker-image financial-showcase-api:local --name financial-showcase
if [[ "$mode" == local ]]; then
  if k -n argocd get application financial-showcase >/dev/null 2>&1; then
    echo 'Argo CD owns this release. Use gitops mode with a published SHA.' >&2; exit 1
  fi
  helm upgrade --install financial-showcase platform/chart --namespace showcase \
    --kube-context "$LAB_CONTEXT" --set-string sourceRevision="$revision" --wait --timeout 300s
  printf '%s\n' 'local-helm-unpublished' > .local/platform-mode
else
  python3 - <<'PY'
import hashlib,urllib.request
from pathlib import Path
p=Path('.cache/platform/argo-cd-10.11.6.tgz')
if not p.exists(): p.write_bytes(urllib.request.urlopen('https://github.com/argoproj/argo-helm/releases/download/argo-cd-10.11.6/argo-cd-10.11.6.tgz',timeout=60).read())
assert hashlib.sha256(p.read_bytes()).hexdigest()=='d8f096d87513b41ff754053a7f9604c943bf29c15436a79226fd51595ea67d05','Argo chart checksum mismatch'
PY
  helm upgrade --install argocd .cache/platform/argo-cd-10.11.6.tgz --namespace argocd --create-namespace \
    --kube-context "$LAB_CONTEXT" --values platform/argocd-values.yaml --wait=legacy --timeout 300s
  python3 - "$revision" <<'PY'
import sys
from pathlib import Path
Path('.local/argocd-application.yaml').write_text(Path('platform/argocd-application.yaml').read_text().replace('SOURCE_REVISION',sys.argv[1]))
PY
  k apply -f .local/argocd-application.yaml >/dev/null
  k -n argocd wait application financial-showcase --for=jsonpath='{.status.sync.revision}'="$revision" --timeout=300s
  k -n argocd wait application financial-showcase --for=jsonpath='{.status.sync.status}'=Synced --timeout=300s
  k -n argocd wait application financial-showcase --for=jsonpath='{.status.health.status}'=Healthy --timeout=300s
  printf '%s\n' "argocd-published:$revision" > .local/platform-mode
fi
k -n showcase rollout status statefulset/postgres --timeout=180s
k -n showcase rollout status deployment/showcase-api --timeout=180s
for deployment in prometheus grafana tempo otel-collector; do
  k -n showcase rollout status "deployment/$deployment" --timeout=180s
done
printf 'Local lab ready: context=%s namespace=%s mode=%s\n' "$LAB_CONTEXT" "$LAB_NAMESPACE" "$mode"
