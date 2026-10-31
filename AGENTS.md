# Working agreement

- Keep progress narration terse. Preserve user-owned work.
- G1 is merged into develop. G2-A prepares Terraform state bootstrap and access
  contracts offline. No AWS provisioning, real cloud credentials, remote Atlantis webhook,
  real financial operations, or paid APIs are authorized by this work.
- renanfenrich owns development and Git flow. main is stable; develop is
  integration; feature/* targets develop. All implementation changes use PRs.
- octavariumdigitalpartners is the mandatory human reviewer and approver.
  Stop at READY FOR HUMAN REVIEW. Never approve your own work. Merge only when
  the owner explicitly authorizes that PR after the mandatory current-head review;
  approval of an earlier PR is not a standing merge authorization.
- Make targets are the shared local/CI contract. Run checks relevant to changes.
- Keep versions pinned; record official source, date, integrity, and compatibility.
- Never commit secrets, Terraform state/plans, database dumps, or raw private logs.
- Evidence must distinguish local runtime, mocked IaC, pending integrations, and
  verified AWS. A passed mock is not a deployed resource or human approval.
- Terraform owns AWS foundations; Argo CD owns application releases. Avoid dual
  ownership. Atlantis G1 has no cloud credentials, kubeconfig, or Docker socket.
