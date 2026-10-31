# Infrastructure source and integrity manifest

Verified 2026-10-30. Stable versions are pinned; no latest image/tag is executed.
Linux amd64 is the supported G1 validation platform. Tool bootstrap pins for
Terragrunt/TFLint are maintained by the repository tool manifest.

| Component | Pin and integrity | Official source / compatibility |
| --- | --- | --- |
| Terraform | `1.17.1`; Linux amd64 archive SHA256 `4638628058e71a55212b1c563712eac03b902128f40740f3dc8174df12135061` | [Release](https://github.com/hashicorp/terraform/releases/tag/v1.17.1), [checksums](https://releases.hashicorp.com/terraform/1.17.1/terraform_1.17.1_SHA256SUMS); same version in toolchain, root and Atlantis |
| AWS provider | `6.71.0`; Linux amd64 archive SHA256 `cb57bbcaf0fa3a70ea29b60d183d3a0dd020f041b18da5d1725d2acd17fa7d59`; committed `.terraform.lock.hcl` records signed-package hashes | [Registry metadata](https://registry.terraform.io/v1/providers/hashicorp/aws/6.71.0/download/linux/amd64), [checksums](https://releases.hashicorp.com/terraform-provider-aws/6.71.0/terraform-provider-aws_6.71.0_SHA256SUMS); actual init/validate/mocked tests verify compatibility with Terraform 1.17.1 |
| Atlantis | `0.49.0`; image `ghcr.io/runatlantis/atlantis:v0.49.0@sha256:389f1c1bf12bd08d647f0383b13cd531e5667a6c654adadf4932d6bf4d5e0c13` | [Release](https://github.com/runatlantis/atlantis/releases/tag/v0.49.0); upstream image no longer bundles Terraform, so the Dockerfile installs the checksum-verified binary |
| Terragrunt | `1.2.1` | [Release](https://github.com/gruntwork-io/terragrunt/releases/tag/v1.2.1), [CLI run reference](https://docs.terragrunt.com/reference/cli/commands/run/); explicitly set `TG_TF_PATH` because the default is OpenTofu |
| TFLint | `0.65.0`, bundled Terraform rules only | [Release](https://github.com/terraform-linters/tflint/releases/tag/v0.65.0); no unpinned external plugin downloads |

Design references: [Terraform test defaults](https://developer.hashicorp.com/terraform/language/tests),
[provider mocking](https://developer.hashicorp.com/terraform/language/tests/mocking),
[validate scope](https://developer.hashicorp.com/terraform/cli/commands/validate),
[provider lock file](https://developer.hashicorp.com/terraform/language/files/dependency-lock),
[S3 backend locking for a later cloud phase](https://developer.hashicorp.com/terraform/language/backend/s3),
[S3 security](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html),
[IAM S3 actions/resource scoping](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_s3_rw-bucket.html),
[KMS key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html),
[S3 SSE-KMS permissions and regional compatibility](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html),
[S3 Bucket Key encryption context](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html),
[VPC security groups](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html),
[provider 6.71.0 security-group rule ownership](https://github.com/hashicorp/terraform-provider-aws/blob/v6.71.0/website/docs/r/security_group.html.markdown).

Atlantis references: [security](https://www.runatlantis.io/docs/security.html),
[trusted server-side config](https://www.runatlantis.io/docs/server-side-repo-config),
[authorization contract](https://www.runatlantis.io/docs/repo-and-project-permissions),
[metrics](https://www.runatlantis.io/docs/stats),
[official fake-credentials startup example](https://www.runatlantis.io/docs/access-credentials),
[disabled API behavior in pinned source](https://github.com/runatlantis/atlantis/blob/v0.49.0/server/controllers/api_controller.go),
[health/readiness in pinned source](https://github.com/runatlantis/atlantis/blob/v0.49.0/server/server.go).
