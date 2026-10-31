# A thin wrapper around the SAME root. G1 invokes init/validate/test, never apply.
terraform {
  source                   = "../../terraform//aws-foundation"
  copy_terraform_lock_file = false
  include_in_copy          = ["**/.terraform.lock.hcl"]
}
