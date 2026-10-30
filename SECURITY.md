# Security boundaries

This repository is an isolated, local-only synthetic-data lab. Do not expose its
API, PostgreSQL, Grafana, Jenkins or Atlantis to a public network. Port-forwards
must bind to 127.0.0.1. API tokens and database/Grafana passwords are generated in
ignored `.local/` files and must never be committed, screenshotted or uploaded.

Report vulnerabilities privately using the repository's private security advisory
channel when available. Do not put credentials or private logs in public issues.
If that channel is unavailable, coordinate a private handoff with the repository
owner. Never publish an exploit containing real data.

`make security` scans code/configuration/dependencies and the application image,
produces an SBOM and fails for HIGH/CRITICAL findings. A false-positive exception
must name the exact rule/resource, explain why it is inapplicable and expire.
Missing scans or skipped integrations are not equivalent to a clean result.
The image gate covers the application image, not every pinned third-party image
in the lab. Atlantis, Jenkins, PostgreSQL and observability images are not declared
vulnerability-free by that result.

No AWS secrets are required. Do not mount ~/.aws, a global kubeconfig, Docker
socket or SCM credentials into Atlantis/Jenkins agents. Plan itself can execute
untrusted provider code; a future public-repository integration needs authorization
before Terraform executes, not merely before apply.
