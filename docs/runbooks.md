# Local demo and recovery

## Start and validate

Run `make doctor bootstrap`, `make verify`, `make image lab-up`, then `make e2e`.
No global packages are installed and no AWS account is required. Downloads require
internet access; runtime data is synthetic. Bootstrap uses checksums from the lock
manifest, and every Kubernetes command selects the dedicated lab kubeconfig.

G1 files:

- `.local/dev.env`: generated API/database credentials, mode 0600.
- `.local/kubeconfig`: access only to this disposable kind cluster.
- `.local/grafana-password`: generated Grafana password, mode 0600.
- `artifacts/`: ignored machine-readable evidence; inspect before any sharing.

## Open the dashboard and API

Use separate terminals for the loopback-only forwards:

```bash
.tools/bin/kubectl --kubeconfig "$PWD/.local/kubeconfig" --context kind-financial-showcase -n showcase port-forward --address=127.0.0.1 service/grafana 13000:3000
```

Open `http://127.0.0.1:13000/d/financial-operations` with user `showcase` and the
password in `.local/grafana-password`. Do not place the password in screenshots or
command arguments. The dashboard presents actual request rates, latency, availability
and open incidents. Tempo is provisioned as a trace data source.

```bash
.tools/bin/kubectl --kubeconfig "$PWD/.local/kubeconfig" --context kind-financial-showcase -n showcase port-forward --address=127.0.0.1 service/showcase-api 18080:8080
```

The token stays in an environment variable. This request deliberately contains
only accepted synthetic fields:

```bash
set -a; source .local/dev.env; set +a
python3 - <<'PY'
import json, os, time, urllib.request
payload = {"system": "synthetic-finance", "component": "payments",
           "type": "failure", "message": "synthetic check failed"}
headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"],
           "Content-Type": "application/json", "Idempotency-Key": "demo-" + str(time.time_ns())}
request = urllib.request.Request("http://127.0.0.1:18080/v1/events",
                                 data=json.dumps(payload).encode(), headers=headers)
with urllib.request.urlopen(request) as response:
    print(response.read().decode())
PY
```

Save the returned incident ID, observe the `SyntheticIncidentOpen` alert, and
resolve it with `POST /v1/incidents/{id}/resolve` using the same authorization.
Replaying the exact event/key returns the original result; changing that payload
under the same key returns 409. Arbitrary message text and additional fields are
rejected. Stop each port-forward with Ctrl-C.

## GitOps

Commit and push the feature branch before running:

```bash
make image
bash scripts/lab-up.sh gitops "$(git rev-parse HEAD)"
bash scripts/lab-e2e.sh --gitops
```

Build the image after committing; GitOps rejects a dirty or mismatched image label.
Argo fetches that immutable published SHA from the public repository. The E2E
exercise scales the API down to one replica and waits for Argo to restore the
declared two replicas. This intentional drift is limited to the local lab.
Once Argo owns the release, do not use the direct local Helm mode.

## Failure and recovery exercise

`make e2e` checks authentication, validation, incident lifecycle, alert firing,
OTLP export, pod replacement, PostgreSQL PVC persistence, least-privilege DB role,
network isolation, and backup restore. The full load profile sends 20 requests/s
for 120 seconds and requires p95 <=500 ms with no failed requests. It records
hardware, duration, latency and errors; this is not a high-scale/cloud SLA.

The suite dumps only the synthetic database in memory and restores it into the
separate `showcase_restore_e2e` database. It validates recovered data and removes
that temporary database afterwards. It never restores over the source database.
Stop writes before taking an operator-managed backup intended for preservation.
Backups and raw credentials must stay outside Git and public artifacts.

If readiness fails, inspect pod readiness, the migration job and database health
inside this context. If network tests fail, inspect Calico readiness and policies;
do not disable enforcement to pass. A failed alert/trace query is failed evidence.
Do not infer a cause solely from a pod being Running.

## Atlantis and Jenkins

`make atlantis-test` builds the pinned image and tests it with no network or mounted
credentials. Health/readiness/metrics and rejected API calls are local checks;
it cannot prove a GitHub PR plan. Read [the infrastructure guide](../infra/README.md)
before preparing a future connection. No apply is allowed in G1.

`make jenkins-test` uses the committed snapshot, verifies the plugin closure,
starts an authenticated loopback-only controller with zero executors, and runs
the Jenkinsfile on a separate inbound agent. It records the actual build number,
result and source SHA. Its own containers/volume are removed after the smoke.
Private failure logs remain in `.local/jenkins/`, outside published artifacts.
Run this heavy profile separately from the main lab when RAM is limited.

## Stop

Stop forwards, then run `make down`. Only the `financial-showcase` kind cluster
and this project's Compose services are removed. Cluster PVC data is disposable;
the Compose PostgreSQL volume and generated credentials are retained. No global
Docker prune, host route/firewall change, or cleanup of other projects is allowed.
