# G1 infrastructure evidence

`make infra-test` validates one AWS foundation root through Terraform and a thin
Terragrunt wrapper. Both execute the same provider-mocked native test suite. This
requires registry access to download the pinned provider but **no AWS credentials,
AWS APIs, backend, bootstrap or provisioning**. Never interpret mock output as
verified AWS capacity, connectivity, permissions or availability. The real local
application runs in kind; it does not use these hypothetical AWS resources.

The foundation describes six /24 subnets across two explicit AZs and three tiers;
private app/data route tables have no default Internet route or NAT. The default
security group denies ingress/egress. PostgreSQL rules reference the application
security group, never a public CIDR. S3 uses Block Public Access, disabled ACLs,
versioning, a customer-managed KMS key with rotation and a 30-day deletion window,
a TLS-only bucket policy and no forced deletions. The unattached IAM policy can only list/read `reports/*`; it creates no
user, access key, role or usable cloud identity.

Before a separately authorized AWS phase: review target account/region, globally
unique bucket name, workload ingress/egress, deployment-role permissions, remote
state with locking, TTL/teardown, budget and logging retention. Enable/review VPC
flow logs, S3 access logging, CloudTrail object data events and CloudWatch metrics.
The KMS key policy delegates management only to the illustrative target account;
report decrypt access is restricted to this bucket through S3. Verify and replace
the illustrative account ID before any future AWS deployment. Storage/requests,
version retention, KMS keys and requests, CloudTrail data events and logs can incur charges if deployed; no
claim of zero-cost AWS operation is made. See [S3 pricing](https://aws.amazon.com/s3/pricing/)
and [CloudTrail pricing](https://aws.amazon.com/cloudtrail/pricing/).

## Atlantis: offline, prepared, not connected

`make atlantis-test` builds the digest-pinned Atlantis image with the pinned
Terraform binary and verified archive checksum. Runtime is non-root, read-only,
capability-free, with bounded tmpfs storage, no host mounts, no cloud credentials,
no kubeconfig and no Docker socket. Runtime uses `--network none`; HTTP probes run
inside the container against `127.0.0.1`, with no published host port. The smoke removes its own container on
exit. Logs and fake VCS placeholders are local test data, never real authentication material.

The smoke proves the image version, trusted server configuration startup,
`/healthz`, `/readyz`, Prometheus `/metrics`, and disabled execution APIs (503).
Authorization tests exercise the actual image-baked script. `allow-commands`
contains only `version,plan`: apply/import/state are disabled for **everyone**,
regardless of approval. A second server-side workflow also refuses apply. PRs
cannot override requirements or define workflows. Forks, autoplan, automerge and
Git credential persistence are disabled.

There is **no GitHub token, App, webhook, remote tunnel, GitHub PR plan or AWS plan
integration**. `atlantis.yaml` declares the future project; its parsing in a real
PR and end-to-end GitHub authorization remain PENDING. `/readyz` with local BoltDB
does not prove GitHub connectivity or authorization. Offline tmpfs is deliberately
not durable; future real PR use requires protected persistent Atlantis data and a
recovery test. Running the CLI mock suite is not an Atlantis PR demonstration.

For a future, separately authorized connection: pin/review the server image,
provide a scoped GitHub App outside Git, authenticate the UI and use HTTPS plus
webhook validation, keep the exact repository allowlist and server-side command
authorization, disable forks, review egress and untrusted Terraform providers/data
sources, and demonstrate rejection before any credentialed plan. Preserve the
current apply deny until an explicit later scope changes it. Before any apply,
require current-head approval by `octavariumdigitalpartners`, protected branches,
passing checks, and a fresh reviewed plan. Codex stops at READY FOR HUMAN REVIEW;
`renanfenrich` owns Git flow and merge follows human approval.
