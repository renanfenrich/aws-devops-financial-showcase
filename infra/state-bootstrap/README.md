# G2-A: offline Terraform state bootstrap

This is a separate, **unprovisioned** root for the eventual AWS state store. It
does not reuse the G1 report-artifact bucket: state can contain confidential
values and needs different access, recovery and ownership controls. Preparing
state storage before EKS/RDS keeps those boundaries reviewable without adding a
large unexercised runtime graph.

`bootstrap_enabled` defaults to `false`; `target` defaults to `null`. Supplying a
target alone does not activate resources. Enabling the graph requires an explicit
account ID, region, globally unique bucket name and same-account IAM role ARN for
key administration. These are future deployment inputs, not values discovered
from the workstation. Their format is checked; account ownership, region support,
bucket availability and role existence remain unverified. G2-A supports the
commercial `aws` partition and ordinary shared-global bucket namespace only.
Names ending `-an` require the separate account-regional creation mode and are
rejected here; that mode has not been selected or validated in this milestone.

The graph switch is not authorization to create resources. No apply target,
remote backend initialization, state migration, role, identity, IAM policy
attachment, OIDC provider, Atlantis connection or AWS API operation is introduced.
Terraform remains pinned to 1.17.1 and the AWS provider to 6.71.0.

## Validation contracts

Run `make state-test` for formatting, initialization with `-backend=false`,
validation, TFLint and the same native Terraform tests through both Terraform and
the thin Terragrunt wrapper. Provider downloads need registry connectivity;
enabled graph tests use **only mocked providers**. All test runs use `command =
plan`; none applies resources. The fixtures' account, region, bucket and role are
explicitly synthetic, not an approved target.

The native tests cover the disabled graph, explicit-target-with-disabled-gate,
bucket/key controls, backend and IAM contracts, alternate state keys, and rejected
account/administrator/region/bucket/path inputs. Mocks do not prove IAM evaluation,
S3 encryption, recovery, native-lock concurrency or AWS runtime behavior.

`make state-plan-test` is a separate Docker-only check of the **real provider's
default disabled graph**. It runs in a network-disabled, read-only container,
with the module, pinned Terraform binary and provider cache mounted read-only.
Only temporary plans use writable `/tmp`. The execution image is selected by its
local content ID; no credential directory or application secrets are mounted.

The provider SDK still requires non-empty credential fields and a parser region,
even with zero resource instances and its network-validation flags disabled.
This check supplies process-local, deliberately nonfunctional SDK fixtures and
an SDK-only region. `target` stays null. A plain real-provider plan without those
fixtures fails credential discovery and is **not** a supported credential-free
workflow. The guarded check requires successful planning and zero resource
changes; a partial JSON plan from a failed command is not passing evidence.
Docker is not required for the mocked test target or the Jenkins/Bitbucket
adapters. No real account or authenticated AWS behavior is established.

## Store and access design

The enabled mock graph describes one dedicated regional KMS key and one S3
bucket, with all four public-access blocks, `BucketOwnerEnforced`, versioning,
SSE-KMS, S3 Bucket Keys and explicitly blocked SSE-C uploads. The key rotates and
has a 30-day deletion window. Bucket and key declare `prevent_destroy`; the bucket
does not permit forced deletion. These protect Terraform operations while the
resource declarations remain in the configuration; they are not protection from
every administrative action or removal of the configuration itself.

The bucket policy denies non-TLS traffic and uploads that do not specify this
KMS key. Terraform 1.17.1 sets the required encryption headers for both state and
lock uploads when its backend is configured with `encrypt = true` and this key's
ARN. No lifecycle expiration, S3 Object Lock retention, replication or recovery
identity is selected. S3 Object Lock is different from Terraform's deletable
`.tflock` object and is not enabled here.

`backend_config` and `backend_access_policy_json` are null when disabled. In the
enabled mock graph they describe a future backend and an **unattached identity
policy**, not an active backend or a trust relationship. The exact state key
defaults to `sandbox/aws-foundation.tfstate`; it must be a relative lowercase path
without traversal, empty segments, wildcards or a lockfile suffix.

The backend contract enables native S3 lockfiles and account restrictions; it
contains no credentials or DynamoDB option. Runtime permissions are restricted to
listing the state prefix, Get/Put on the exact state object, and Get/Put/Delete on
its exact `.tflock` object. It grants neither deletion/version-deletion of the
state nor broad workspace access. KMS permissions address this key only, through
regional S3, with the target caller account and the bucket ARN as encryption
context because S3 Bucket Keys are enabled.

Only the default Terraform workspace is supported. Leave the backend's workspace
prefix unchanged: pinned Terraform tolerates denial of its default non-default
workspace listing, but this is not permission to use additional workspaces.
Select another explicit key for a future separately reviewed root/environment.
The backend identity contract is distinct from permissions to deploy workloads
or administer the key. The key policy preserves target-account IAM delegation
and names an explicit administrator; no identity is created or attached here.

## Before any future activation

This milestone leaves AWS activation and remote Atlantis/PR execution pending.
A later approved scope must verify target identity, select the execution/trust
model, review costs and resource lifetime, determine state/version retention and
teardown ownership, and validate the access policies against real APIs.

The bootstrap cannot initially use the bucket it has not created. Its initial
local-state custody and any later migration require a separate reviewed
procedure, backups and a recovery test. Existing foundation/local application
state is not migrated by G2-A. Keep all state, raw plans and credentials outside
Git and published artifacts.

The [offline state-recovery drill](../../docs/state-recovery.md) defines
`make state-recovery-test` using generated synthetic local state and native CLI
rejection checks. Its proposed custody procedure does not authorize real state
handling, backend activation or migration, and does not prove encrypted custody.

Before production use, review access logging, CloudTrail state-object data
events, monitoring and alarms. Bucket creation, retained object versions,
requests and the KMS key/operations can incur charges when activated; neither
offline tests nor this design prove a zero AWS bill. No retention/cost decision
or cloud restore/RPO/RTO result is implied. See [official sources](SOURCES.md),
[the roadmap](../../docs/roadmap.md) and the [G1 boundary](../README.md).
