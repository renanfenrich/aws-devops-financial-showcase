# Published G1 evidence

These sanitized records were copied from successful local runs against clean code
revision `f1603b3493789414fdde771eef1795db4966adf4`. The publication commit adds only
documentation/evidence; it does not change the verified application or harness.

- [Core gate](g1/core.json): source content hashes, versions, command outcome and report hashes.
- [Offline Atlantis](g1/atlantis.json): the actual smoke command passed; PR/webhook E2E remains pending.
- [Runtime](g1/runtime.json), [benchmark](g1/benchmark.json) and [E2E gate](g1/e2e-gate.json).
- [OCI provenance](g1/oci-provenance.json): exported index, scanned index, platform
  manifest and image config were verified byte-for-byte against the kind content store.
- [Real Jenkins build](g1/jenkins.json) and [Jenkins gate](g1/jenkins-gate.json).
- [Security scan](g1/security.json) and [security gate](g1/security-gate.json): filesystem and API image only.
- [GitHub CI](g1/github-ci.json): completed remote run for the tested code revision.

Raw scanner matches, environment files, database dumps and private failure logs
are excluded. Full source-bound run histories remain in ignored `artifacts/history/`.
Fresh CI runs attach sanitized artifacts to the PR; those artifacts have limited
retention, while these committed summaries remain reviewable.

An OCI image index, its platform manifest and its config can have different IDs.
Runtime pointer `711575…` is the outer export/import index, scanned `8d889…` is
the nested Docker index, `e427ec…` is the platform manifest and `be4c85…` its config.
The local load path selects one replica
through port-forward and does not establish load balancing or cloud capacity.
Restore timing describes a paused-write local logical snapshot, not cloud RPO/RTO.
