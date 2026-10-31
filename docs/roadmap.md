# Milestones and acceptance

## G1: local scenario and development harness

Deliver a reproducible incident lifecycle, secure local Kubernetes deployment,
observable failures, repeatable restore, measured load and reviewable infrastructure
tests. Completion requires actual gate results and a ready PR with the mandatory
reviewer. It does not authorize merging or AWS activation.

The task contract is: read AGENTS.md and the relevant source ledger; change one
bounded subsystem; run its Make gate; attach evidence and remaining limitations;
request review. No agent framework, paid API or external memory service is needed.

## G2: scoped AWS runtime (not authorized by G1)

- Confirm account identity, region, allowed cost envelope, resource lifetime and
  teardown/backup ownership before provisioning. Estimate costs from current prices.
- Bootstrap state separately: private encrypted/versioned S3 with native lockfiles;
  short-lived access, trusted Atlantis installation and a controlled real PR plan.
- EKS with EC2 managed nodes, private workload/data subnets, RDS PostgreSQL Multi-AZ,
  ALB, HPA and node scaling. Verify the add-on/version matrix before implementation.
- Pod Identity, Secrets Manager, CloudWatch, CloudTrail and OTel export to X-Ray.
- Restore RDS to a new instance, measure recovery, exercise a bounded incident,
  and review cost/availability/security against the Well-Architected pillars.

## G3: bounded extensions (not authorized by G1)

- Bedrock managed Knowledge Base for approved runbooks, with retrieval evaluation,
  data boundaries and injection-resistant handling of retrieved content.
- SageMaker batch inference over synthetic telemetry; no persistent endpoint until
  justified by an explicit latency/cost requirement.
- Amplify portal for the demonstration; CloudFormation change-set/drift exercise
  managing separate resources; SonarQube quality analysis in a separate profile.
- Bitbucket SaaS pipeline and a real Atlantis webhook/PR workflow only after the
  integration credentials, exposure and permission model are reviewed.

Every milestone updates the matrix with observed evidence. Certification,
production experience, financial compliance and high-scale operation remain
independent claims requiring their own evidence.
