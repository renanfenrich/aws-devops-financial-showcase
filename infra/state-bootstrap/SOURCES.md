# G2-A source and compatibility record

Researched **2026-10-31 UTC** (2026-10-30 in America/Sao_Paulo). No version upgrade
is required for this milestone. The [copied provider lock](../terraform/state-bootstrap/.terraform.lock.hcl)
matches the G1 canonical lock; exact binary integrity remains in the
[toolchain manifest](../../toolchain.lock.json) and [infrastructure ledger](../SOURCES.md).

| Component / behavior | Primary source and verified consequence |
| --- | --- |
| Terraform 1.17.1 S3 backend | [Backend reference](https://developer.hashicorp.com/terraform/language/backend/s3): native locking is opt-in via `use_lockfile`; bucket versioning is recommended; DynamoDB locking is deprecated. State Get/Put and lock Get/Put/Delete are distinct. Backend credentials do not belong in configuration or plan files. |
| Pinned core encryption implementation | [1.17.1 S3 client](https://github.com/hashicorp/terraform/blob/v1.17.1/internal/backend/remote-state/s3/client.go): both state and native-lock uploads set SSE-KMS/key headers when configured with encryption and a KMS key ID. Native locking uses a conditional write; mocked infrastructure tests do not exercise it. |
| Default-workspace limitation | [1.17.1 workspace implementation](https://github.com/hashicorp/terraform/blob/v1.17.1/internal/backend/remote-state/s3/backend_state.go): access denial when listing the default non-default-workspace prefix is handled by returning the default workspace. A custom prefix does not have that fallback. No extra workspace permissions are granted. |
| Mock behavior | [Terraform provider mocking](https://developer.hashicorp.com/terraform/language/tests/mocking): `override_during = plan` supplies deterministic computed key ARNs without mock apply or cloud operations. Plan-only test runs validate this root's contracts. |
| Provider 6.71.0 S3 encryption | [Pinned provider resource](https://github.com/hashicorp/terraform-provider-aws/blob/v6.71.0/website/docs/r/s3_bucket_server_side_encryption_configuration.html.markdown): supports SSE-KMS, bucket keys and `blocked_encryption_types = ["SSE-C"]`. Deleting its encryption resource resets bucket defaults; it is not equivalent to deleting the bucket. |
| Provider 6.71.0 KMS | [Pinned key resource](https://github.com/hashicorp/terraform-provider-aws/blob/v6.71.0/website/docs/r/kms_key.html.markdown): key policy has one owner in this configuration; rotation and the 30-day deletion window are explicit. |
| S3 protection | [Security best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html), [versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html): private access, disabled ACLs, recoverable object versions and separately reviewed audit controls. No real recovery is claimed. |
| Bucket naming | [Current naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html): reserved prefixes/suffixes are rejected. G2-A uses the shared-global namespace; `-an` names require account-regional creation mode and are not accepted by this contract. |
| S3 policy action/resource types | [Required API permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html): bucket listing addresses a bucket ARN; object access addresses exact object ARNs. The JSON output is an identity-policy contract, not an attached grant. |
| KMS delegation / administration | [Default key policy](https://docs.aws.amazon.com/kms/latest/developerguide/key-policy-default.html): key policies must deliberately preserve target-account IAM delegation; key administrators and cryptographic users are separate concepts. `Resource: "*"` inside this key policy refers to this key. |
| Bucket Key encryption context | [S3 Bucket Keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html), [KMS policy example](https://docs.aws.amazon.com/fsx/latest/LustreGuide/s3-server-side-encryption-support.html): bucket-key use changes the S3 encryption context to the bucket ARN, which is reflected in the backend access policy. |
| Future cost | [S3 pricing](https://aws.amazon.com/s3/pricing/), [KMS pricing](https://aws.amazon.com/kms/pricing/): stored versions, requests, keys and cryptographic operations can be billable; no account-specific estimate or cost authorization exists. |

The real-provider disabled-plan check uses synthetic SDK fields solely inside a
network-disabled container. Its zero resource graph is evidence about local
configuration, not authenticated AWS state. Enabled planning uses mock providers
only. Cloud account discovery, live trust setup, policy simulation, backup/restore,
locking contention, AWS deployment and Atlantis webhook execution remain pending.
