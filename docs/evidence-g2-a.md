# G2-A verification record

Verified on **2026-10-31 UTC** against clean code revision
[`e3951d995125c81537782886a12775c6ed5bebda`](https://github.com/renanfenrich/aws-devops-financial-showcase/commit/e3951d995125c81537782886a12775c6ed5bebda).
All five gate records have identical start/end source hashes and zero exit codes.
The publication commit adds documentation/evidence only.

## What changed

The dedicated, unactivated state-bootstrap root defaults to a disabled graph and
null target. Its enabled mock describes private versioned S3/KMS storage, an
inactive native-lock backend contract and exact state/lock access policies.
Atlantis requires the approved foundation project/directory at project execution;
bootstrap and unknown projects are denied. Native tests and shared CI adapters
include the new root, while the Docker-only plan check stays outside Jenkins and
Bitbucket's no-Docker contracts.

## Observed gates

| Gate | Result and durable record |
| --- | --- |
| `make evidence GATE=core` | 34 pytest items passed, with additional unittest authorization subcases; application/database regression, lint, chart/alert and workflow contracts passed. [Record](../evidence/g2-a/core-gate.json). |
| Terraform / Terragrunt | The 8 existing foundation cases and 24 state-bootstrap cases passed through each runner; no mock apply or AWS API. Both roots passed validation and TFLint. |
| `make evidence GATE=state-plan` | The real provider planned successfully with zero resource instances/changes, disabled switch, null target and known-null backend/policy outputs. Networking was physically disabled; SDK fields were deliberately nonfunctional fixtures. [Plan](../evidence/g2-a/disabled-plan.json), [gate](../evidence/g2-a/state-plan-gate.json). |
| `make evidence GATE=atlantis` | Actual isolated image smoke passed, including both authorization stages, approved foundation access, bootstrap/unknown/traversal denials, mutating-command denials and disabled APIs. [Record](../evidence/g2-a/atlantis-gate.json). |
| `make evidence GATE=security` | Updated filesystem/dev-dependency/configuration and immutable API-image scans passed with no HIGH/CRITICAL findings; SBOM generated. [Summary](../evidence/g2-a/security.json), [gate](../evidence/g2-a/security-gate.json). This does not certify every third-party image or an enabled AWS deployment. |
| `make evidence GATE=jenkins` | Actual isolated Jenkins pipeline SUCCESS, 33.429 seconds, same source SHA, zero controller executors and no host Docker socket/cloud credentials. [Build](../evidence/g2-a/jenkins.json), [gate](../evidence/g2-a/jenkins-gate.json). |

## Boundaries

The real-provider plan is not a plain credential-free command: the SDK requires
parser fields even when no resources exist. The guarded runner supplies fixtures
only in its network-disabled process. It copies regular Terraform code and the
provider lock, excluding workstation tfvars/state/backend caches; temporary plan
files are removed and only safe JSON summaries are published. An initial assertion
that confused present null outputs with absent outputs was corrected; its private
failed diagnostic was retained before the successful clean-source gate.

The enabled graph remains provider-mocked. Account/region/role/bucket existence,
IAM evaluation, actual S3 locking contention, encryption, state migration and
cloud recovery are unverified. No IAM identity or policy attachment, remote
backend, credential, webhook, apply or AWS resource was activated.

G1 application, database, container, Kubernetes/chart and pinned dependencies are
unchanged from the reviewed develop base. Its runtime/E2E/benchmark records retain
their original SHA and were not relabeled or rerun for this infrastructure change.
The [approved G1 merge](../evidence/g1/merge.json) is separate from review of G2-A.
