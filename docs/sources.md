# Official documentation ledger

Research date: **2026-10-30**. Exact downloaded binaries and archive checksums are in
[toolchain.lock.json](../toolchain.lock.json); Python packages/hashes are in
[uv.lock](../uv.lock). Container digests are embedded in Docker/Compose/chart files.
Read the subsystem ledgers for version-specific constraints and image provenance.
The final application runtime uses the official Python 3.14.10 Alpine 3.24 image;
unused pip/ensurepip are removed. Debian alternatives were scanned and rejected
because of unresolved HIGH/CRITICAL base-package findings, not silently ignored.

| Component | Official reference and decision |
| --- | --- |
| Python 3.14.10 | [Release](https://www.python.org/downloads/release/python-31410/); supported interpreter shared by local tools and image |
| uv 0.13.6 | [Release](https://github.com/astral-sh/uv/releases/tag/0.13.6); frozen dependency installation |
| FastAPI 0.162 | [OpenTelemetry](https://fastapi.tiangolo.com/advanced/opentelemetry/), [testing](https://fastapi.tiangolo.com/tutorial/testing/); native instrumentation, no duplicate instrumentor |
| Psycopg / pool | [Transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), [pool](https://www.psycopg.org/psycopg3/docs/advanced/pool.html); bounded connections and atomic writes |
| PostgreSQL 18.6 | [Version policy](https://www.postgresql.org/support/versioning/), [backup](https://www.postgresql.org/docs/18/backup-dump.html); current supported stable major, actual restore exercise |
| Terraform / Terragrunt / Atlantis | [Infrastructure ledger](../infra/SOURCES.md), [G2-A ledger](../infra/state-bootstrap/SOURCES.md); exact versions, native locking, mocking boundary and trusted project authorization |
| kind / Kubernetes / Calico / Helm / Argo | [Platform ledger](../platform/SOURCES.md); tested compatibility intersection and pinned images |
| OpenTelemetry | [Python SDK](https://opentelemetry.io/docs/languages/python/); OTLP traces with bounded metadata |
| Prometheus | [Instrumentation](https://prometheus.io/docs/practices/instrumentation/); low-cardinality route metrics |
| Grafana / Tempo | [Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/), [Tempo](https://grafana.com/docs/tempo/latest/); configuration as code and queryable local traces |
| Jenkins | [Controller isolation](https://www.jenkins.io/doc/book/security/controller-isolation/), [pipeline practices](https://www.jenkins.io/doc/book/pipeline/pipeline-best-practices/); zero controller executors, separate agent |
| Jenkins plugins | [Pinned closure](../ci/jenkins/plugins.lock.json); official update-center SHA-256 for every plugin |
| Bitbucket | [Step options](https://support.atlassian.com/bitbucket-cloud/docs/step-options/); adapter only, SaaS execution pending |
| GitHub Actions | [Secure use](https://docs.github.com/en/actions/reference/security/secure-use); SHA pins, read-only token, no privileged PR trigger |
| Trivy | [Documentation](https://trivy.dev/docs/latest/), [security incident](https://github.com/aquasecurity/trivy/discussions/10462); current checksum-verified release and no cloud credentials |
| AWS | [Well-Architected](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html), [X-Ray migration](https://docs.aws.amazon.com/xray/latest/devguide/xray-daemon.html); later cloud verification remains explicit |

Update pins through a PR: verify source/integrity, check compatibility, rerun the
relevant gate and record the new SHA/results. An automated dependency PR is not
approval to activate infrastructure or accept a security exception.
