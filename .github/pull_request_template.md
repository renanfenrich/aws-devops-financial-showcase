## Change

Describe the behavior and the requirement this proves.

## Validation

List commands actually run and their outcome for this SHA.

## Infrastructure diagram

- [ ] Infrastructure changes are reflected in the Archify views using official AWS icons.
- [ ] `make diagram-check` passes; if topology is unchanged, provenance records the
  revalidation reason (`make diagram-refresh NOTE="..."`).
- [ ] Diagram evidence distinguishes local runtime, mocked IaC and unprovisioned AWS.

## Evidence boundaries

Distinguish local runtime, mocked IaC, pending integrations, and verified AWS.
No AWS provisioning or real financial data is authorized in G1.

## Human review

Required reviewer: @octavariumdigitalpartners. READY FOR HUMAN REVIEW does not
authorize a merge or deployment.
