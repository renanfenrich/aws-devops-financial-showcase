# Local platform source and integrity record

Verified 2026-10-30 against upstream documentation, release artifacts and registry
manifest digests. This record describes the local lab; it does not claim AWS
deployment, Multi-AZ availability, disaster recovery in AWS, or high-scale results.

| Resource | Selected version and source | Integrity and compatibility |
| --- | --- | --- |
| kind | [0.33.0 release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0) | Node image 1.36.4 SHA-256 `099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed`; default 1.37 is deliberately not used. |
| Calico | [3.33.0 release](https://github.com/projectcalico/calico/releases/tag/v3.33.0), [kind installation](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind), [requirements](https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements) | Upstream manifest SHA-256 `2de8f47595fb9c41b3f47d7b767a1f8e72ecf84057af834738ff12689a234da5`; exact image digests in lab-up.sh. Kubernetes 1.36 is upstream tested. VXLAN and the pod CIDR are the explicit local adaptations. |
| Helm | [4.2.1](https://github.com/helm/helm/releases/tag/v4.2.1) | Matches the renderer [embedded in Argo CD 3.5.6](https://github.com/argoproj/argo-cd/blob/v3.5.6/hack/tool-versions.sh). Tool integrity is recorded in the root toolchain lock. |
| Argo CD | [3.5.6](https://github.com/argoproj/argo-cd/releases/tag/v3.5.6), [chart 10.11.6](https://github.com/argoproj/argo-helm/releases/tag/argo-cd-10.11.6), [tested Kubernetes versions](https://argo-cd.readthedocs.io/en/stable/operator-manual/tested-kubernetes-versions/) | Chart SHA-256 `d8f096d87513b41ff754053a7f9604c943bf29c15436a79226fd51595ea67d05`; image digests in argocd-values.yaml. One allowlisted repository, namespace and exact Git SHA. |
| PostgreSQL | [18.6 version policy](https://www.postgresql.org/support/versioning/), [official image](https://hub.docker.com/_/postgres) | Chart pins the multi-architecture digest. The API role cannot create roles/databases or become superuser. One local PVC is not a highly available database. |
| Prometheus | [3.15.1](https://github.com/prometheus/prometheus/releases/tag/v3.15.1), [instrumentation](https://prometheus.io/docs/practices/instrumentation/), [rule tests](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/) | Image digest in chart values. Two-hour/128 MB retention; bounded route labels; alert tests run with promtool. |
| Grafana | [13.3.0](https://github.com/grafana/grafana/releases/tag/v13.3.0), [file provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) | Image digest in chart values. Provisioned dashboard/datasources, generated local password, no public ingress or anonymous access. |
| Tempo | [3.1.1](https://github.com/grafana/tempo/releases/tag/v3.1.1), [configuration](https://grafana.com/docs/tempo/latest/configuration/) | Image digest in chart values. Single binary, local ephemeral storage and one-hour trace retention. |
| OTel Collector | [0.164.0](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.164.0), [configuration](https://opentelemetry.io/docs/collector/configuration/) | Image digest in chart values. HTTP OTLP input, batch/memory limits and internal Tempo export; API uses FastAPI native tracing rather than duplicate instrumentors. |
| BusyBox | [official image](https://hub.docker.com/_/busybox) | 1.37.0 digest pinned in chart values and E2E probe. Used only for short-lived network tests. |

The application image `financial-showcase-api:local` is built locally and loaded
into the named kind cluster. Its immutable image ID is evidence from the build;
the local tag is not a published registry artifact. Argo CD only adopts the
application after the chosen source SHA is published. Local Helm bootstrap and
an exact-SHA GitOps test are recorded as separate evidence states.

Argo bootstrap selects Helm 4's documented `--wait=legacy` readiness strategy.
In this lab Helm 4.2.1's watcher strategy remained pending before creating a
nonexistent pre-install hook resource; legacy polling created the hook promptly.
This affects bootstrap waiting, not Argo's Helm manifest rendering. See the
[Helm upgrade wait strategies](https://helm.sh/docs/helm/helm_upgrade/). Failed
bootstrap attempts are retained separately from successful runtime evidence.

All kubectl/Helm commands select `.local/kubeconfig` and
`kind-financial-showcase`. NetworkPolicy enforcement is tested with both an
allowed database client and a denied client; merely installing YAML is not
accepted as enforcement evidence. Calico's node privileges are confined to the
disposable kind node container, with no host firewall or service changes.
