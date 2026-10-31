# Thin wrapper around the SAME root; no remote_state block or bootstrap action.
terraform {
  source                   = "../../terraform//state-bootstrap"
  copy_terraform_lock_file = false
  include_in_copy          = ["**/.terraform.lock.hcl"]
}
