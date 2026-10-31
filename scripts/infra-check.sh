#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$ROOT/.tools/bin:$PATH"
export TF_IN_AUTOMATION=true TF_INPUT=false AWS_EC2_METADATA_DISABLED=true
export AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null TF_CLI_CONFIG_FILE=/dev/null
export TF_PLUGIN_CACHE_DIR="$ROOT/.cache/terraform/providers"
mkdir -p "$TF_PLUGIN_CACHE_DIR"
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN
cd "$ROOT"
[[ "$(terraform version -json | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')" == 1.17.1 ]]
[[ "$(terragrunt --version)" == 'terragrunt version v1.2.1' ]]
[[ "$(tflint --version)" == 'TFLint version 0.65.0'* ]]
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/aws-foundation init -backend=false -input=false -lockfile=readonly -no-color
terraform -chdir=infra/terraform/aws-foundation validate -no-color
terraform -chdir=infra/terraform/aws-foundation test -no-color
tflint --chdir=infra/terraform/aws-foundation --config="$ROOT/.tflint.hcl"
# Terragrunt defaults to OpenTofu in this release; explicitly use the pinned Terraform.
export TG_TF_PATH="$(command -v terraform)"
terragrunt --working-dir infra/terragrunt/aws-foundation --non-interactive run --source-update -- init -backend=false -input=false -lockfile=readonly -no-color
TG_NO_AUTO_INIT=true terragrunt --working-dir infra/terragrunt/aws-foundation --non-interactive run -- validate -no-color
TG_NO_AUTO_INIT=true terragrunt --working-dir infra/terragrunt/aws-foundation --non-interactive run -- test -no-color
python3 -m unittest discover -s tests/infra -p 'test_*.py' -v
printf '%s\n' 'IaC passed: Terraform/Terragrunt mocked tests and trusted authorization; no AWS API/deployment.'
