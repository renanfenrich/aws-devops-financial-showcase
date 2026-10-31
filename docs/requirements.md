# Requirement-to-evidence matrix

Source: [South System DevOps role, Jobii 2491](https://vagas.jobii.com.br/vagas/2491),
read on 2026-10-30. The listing identifies Pleno/Sênior and describes senior DevOps
responsibilities. This table paraphrases its requirements without reproducing it.

| Requirement | G1 deliverable | Evidence boundary |
| --- | --- | --- |
| AWS architecture / Well-Architected | Ownership decisions, risk boundaries, staged cloud design | Design review; no AWS runtime |
| Terraform / Terragrunt | Foundation and state-bootstrap roots, provider-mocked invariants and disabled-plan isolation | Mocked enabled designs; zero-resource real-provider plan only |
| IAM / VPC / S3 | Restricted policy, segmented AZ subnets, private encrypted bucket | Mocked IaC only |
| Docker / Kubernetes / Helm | API image, kind, Calico, chart, probes and resources | Local runtime |
| GitOps / Argo CD | Published-SHA release and drift correction | Local runtime after Git publish |
| DevOps / CI/CD | Shared Make contract, GitHub Actions, isolated Jenkins pipeline | Local execution; remote CI separately recorded |
| Bitbucket / Pipelines | Adapter invoking shared commands | Config and command validation; SaaS pending |
| Atlantis | Pinned image, trusted project/path allowlist, bootstrap rejection and server smoke | PR/webhook plan E2E pending |
| Prometheus / Grafana | Metrics, alert rules, dashboard and bounded cardinality | Local runtime |
| CloudWatch / CloudTrail / X-Ray | OTel-compatible design and future AWS export | Cloud integration planned |
| Fault tolerance / scaling / balancing | API replicas, restart recovery and measured load | Local experiment; no cloud HA claim |
| Backup / DR | PostgreSQL backup and separate-database restore | Local restore only |
| Operational automation | Scripted fault, alert, recovery and evidence collection | Bounded local exercise |
| Cost optimization | No-provision default, resource limits, sequential heavy profiles | Local safeguards; no AWS bill measured |
| EC2 / EKS / RDS / Lambda | G2 architecture and explicit activation gates | Planned |
| Bedrock / Knowledge Base / SageMaker | Runbook retrieval and batch-analysis design in G3 | Planned; no model/API calls |
| Amplify / CloudFormation / SonarQube | Isolated follow-on exercises | Planned |
| Financial-sector context | Synthetic operational events, auditability and recovery | Technical simulation; no employment claim |
| Collaboration / communication | Architecture decisions, runbooks, PR review and evidence boundaries | Repository artifacts |
| Certification / high-scale experience | Not claimed by this repository | Requires independent credentials/history |

See [verification](evidence-g1.md) for actual outcomes. A configured feature is not
automatically tested; a mock is not a deployed service; CI is not human approval.
