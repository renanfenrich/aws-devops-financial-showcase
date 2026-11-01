# Offline Terraform state recovery

This runbook defines a synthetic recovery drill and a proposed custody procedure.
It does not authorize recovery of real state, an AWS operation, backend activation
or migration. The [state-bootstrap root](../infra/state-bootstrap/README.md)
remains disabled. Real custody, encryption, retention, owners and recovery approval
must be selected separately before any future activation.

## Reproduce the drill

Use the repository's checksum-pinned Terraform **1.17.1**, recorded in
[toolchain.lock.json](../toolchain.lock.json) and the
[infrastructure ledger](../infra/SOURCES.md). Installing the pinned toolchain may
require downloads; the drill itself requires no provider or cloud access.

```bash
make state-recovery-test
make evidence GATE=state-recovery
```

The target accepts no paths to real state or existing working directories. It is
a test harness, not an operator backup/restore command. Its required contract is:

1. Create new temporary directories with mode `0700` and generated synthetic state
   files with mode `0600`. Use an isolated CLI environment and only Terraform's
   default local state behavior, with no configuration, provider, backend
   initialization or inherited workspace selection.
2. Run real `terraform state pull` and `terraform state push` only in those
   directories. Capture state output privately rather than printing it. Preserve
   a backup and its SHA-256 digest; verify the digest before restoring to a new,
   empty destination.
3. Verify the restored synthetic content. Reject a deliberately corrupted backup
   through the checksum gate. Exercise Terraform's native differing-lineage and
   older-source-serial rejections against the restored disposable destination.
   Never use `-force` or bypass a rejection; verify rejected writes leave the
   destination unchanged and the original backup remains unchanged.
4. Remove temporary state, backups and diagnostics in `finally`, including on
   failure. Publish only boolean check results, with no state values, state
   digests, local paths or raw Terraform output. Cleanup failure is a failure.

These are acceptance requirements, not an assertion that a run has passed.
Attach observed results to the tested source revision before reporting success.
Existing [G2-A evidence](evidence-g2-a.md) does not cover this new drill.

The drill can establish local CLI recovery and refusal behavior for synthetic
fixtures. It cannot establish encrypted custody, durable backup retention,
secure erasure, real RPO/RTO, S3 recovery, IAM evaluation, remote locking or a
working migration. A checksum detects a mismatch against a trusted digest; it
provides neither authentication nor encryption. Replacing both bytes and digest
can defeat that check. File modes and cleanup are not encryption or secure erasure.

## Proposed operational procedure: approval still pending

This sequence is for a future reviewed recovery plan. It supplies no command to
write real state and must not be executed against a real backend under this scope.

1. **Freeze writers.** Identify the exact root, workspace, backend, source revision
   and Terraform version. Stop all automation and operator writes; establish the
   incident owner and approval record. Investigate any outstanding lock instead
   of automatically unlocking it.
2. **Select custody.** Before the initial bootstrap creates any real local state,
   agree on encrypted storage outside Git, key access and recovery, a named
   custodian, retention, permitted readers and teardown/backup ownership. Keep
   state, plans and private diagnostics out of public artifacts.
3. **Preserve the source.** Retain the original and an immutable backup with a
   separately protected checksum and private provenance record. Record the
   generating version and state identity before any conversion. A pull can
   normalize the copy to the installed Terraform version; it is not evidence of
   the original writer's version. Do not edit the sole surviving copy.
4. **Verify recovery separately.** After explicit authorization to handle that
   backup, verify its checksum, decrypt only within approved custody, and test a
   copy in a new isolated directory. Keep the original unchanged. Validate the
   recovered content privately; release only a sanitized result.
5. **Respect native guards.** Compare the intended destination's lineage and
   serial within the approved recovery plan. A mismatch stops the procedure;
   do not rewrite metadata, lower a serial or force a write to make it pass.
6. **Defer the real write.** Actual `state push`, remote backend initialization,
   migration, unlock or resumed automation requires a separately approved plan,
   target identity, rollback/custody arrangements and current-head human review.
   The synthetic target grants none of those permissions.

`renanfenrich` owns development and Git flow. Stop at READY FOR HUMAN REVIEW;
`octavariumdigitalpartners` supplies the mandatory current-head review. A local
test result is not that approval or authorization to activate resources.

## Official sources and compatibility

Consulted **2026-11-01**. HashiCorp's current references describe the 1.17.x CLI;
this repository keeps **1.17.1** pinned and requires observed behavior from that
binary. No tool or provider upgrade is introduced by this procedure.

| Official reference | Consequence for this contract |
| --- | --- |
| [State pull](https://developer.hashicorp.com/terraform/cli/commands/state/pull) | Reads local or remote state and emits a normalized raw copy; capture it privately and keep the original backup intact. |
| [State push](https://developer.hashicorp.com/terraform/cli/commands/state/push) | Writes to the configured destination. Differing lineage and a higher destination serial block unsafe writes; the drill exercises those guards without `-force`. |
| [Recover state from backup](https://developer.hashicorp.com/terraform/cli/state/recover) | Recovery includes understanding lock state, reading and writing state. Unlocking overrides concurrency protection and is not part of this drill. |
| [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) | State may contain secrets; local state is plaintext, and `sensitive` redaction does not encrypt stored values. Real encrypted custody remains a separate prerequisite. |
