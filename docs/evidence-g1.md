# G1 verification record

Verified on **2026-10-30**, against clean code revision
[`f1603b3493789414fdde771eef1795db4966adf4`](https://github.com/renanfenrich/aws-devops-financial-showcase/commit/f1603b3493789414fdde771eef1795db4966adf4).
Every gate recorded identical starting/ending source hashes and a zero exit code.
This publication changes documentation/evidence only. See the
[committed evidence index](../evidence/README.md) for machine-readable records.

| Gate | Observed result |
| --- | --- |
| `make evidence GATE=core` | Ruff, formatting, repository/workflow contracts, 30 Python tests, real PostgreSQL integration, IaC and chart/rule checks passed. Application line coverage: 92.24%. |
| Terraform / Terragrunt | The same 8 provider-mocked cases passed through each runner; TFLint and authorization checks passed. No AWS API or resource creation. |
| `make evidence GATE=atlantis` | Real isolated server smoke passed: version, health/readiness, metrics, execution APIs disabled, mutating commands rejected. |
| `make evidence GATE=security` | Updated Trivy filesystem/dev-dependency/IaC and immutable API-image scans passed with zero HIGH/CRITICAL findings; SBOM generated. Other third-party images were not covered by this image gate. |
| `make evidence GATE=e2e` | 15 runtime checks passed, including exact-SHA image/manifests, Argo drift correction, Calico, database recovery and observability. |
| `make evidence GATE=jenkins` | Real Jenkins pipeline SUCCESS in 27.067 s, separate agent, zero controller executors, no cloud/SCM credentials or Docker socket. |
| GitHub CI | [Remote run passed](https://github.com/renanfenrich/aws-devops-financial-showcase/actions/runs/41144700363); PR title and GitGuardian also passed on the tested code revision. Current-head status is visible on the PR. |

## Measured local behavior

- **Load:** 2,400 accepted event writes, 20 requests/s for 120 seconds; p95
  **4.564 ms**, no non-201 responses, no HTTP 5xx and no transport errors. The
  connection used port-forward to one replica. This does not prove balancing,
  Multi-AZ availability or high-scale cloud performance.
- **Recovery:** API and PostgreSQL pod replacements preserved records. A separate
  database restore matched counts and ordered-row digests; local restore measured
  **0.666 s**, with writes paused and zero rows lost relative to that snapshot.
- **Security:** application DB role had no superuser/create-role/create-database
  privileges; API service account could not read Secrets; allowed/denied database
  connections and DNS behavior matched the enforced Calico policy.
- **Observability:** a real persisted incident fired the alert; its trace was
  queryable in Tempo; Prometheus scraped two healthy API targets; authenticated
  Grafana API returned the provisioned four-panel dashboard.
- **GitOps:** Argo reconciled the published source SHA and restored the declared
  two replicas after a deliberate local scale change. Image provenance was checked
  against source labels and the loaded/runtime image identifiers.

## Corrections and boundaries

Validation exposed and corrected Helm 4 bootstrap waiting, Tempo 3 configuration,
Grafana memory sizing, a Git-metadata assumption in the Jenkins snapshot, and a
missing `rg` dependency on the GitHub runner. Interrupted/failed attempts remain
in local run history; they are not substituted for successful evidence.

GitGuardian initially classified Compose interpolation syntax as passwords.
Complete container DSNs now come from the generated private environment, and
required-variable expressions contain no command text. The own feature commits
were consolidated with local backup refs retained; the clean PR scan passed.
No actual credential was committed, no detector was disabled, and no secret
exception was added.

AWS runtime, real Atlantis GitHub webhook/PR plan, Bitbucket SaaS, cloud HA/DR,
cloud cost measurements, certification, human approval and merge remain separate
and are not claimed. No AWS provisioning was performed.

## Reviewed merge, 2026-10-31 UTC

After the verification above, `octavariumdigitalpartners` approved PR #1 on head
`767ac6fb1d2e09d20bcbc279276f00900e7b6698`. With explicit owner authorization,
the PR was squash-merged into develop as
`b0e38eba0f73bd6f25a037977a7d114d6902f72e`. The merged tree matches the approved
head. Only documentation/evidence differs from the runtime-tested `f1603b3`;
application and harness code is unchanged. The historical gate JSON is not relabeled.
See the [merge record](../evidence/g1/merge.json). This is a develop merge, not a
main promotion, deployment, AWS activation or approval of a subsequent PR.
