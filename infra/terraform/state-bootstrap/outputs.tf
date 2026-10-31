output "backend_config" {
  description = "Unactivated non-secret backend contract for one default-workspace state. Never includes credentials; null while disabled."
  value = !local.enabled ? null : {
    bucket              = var.target.bucket_name
    key                 = var.state_key
    region              = var.target.region
    encrypt             = true
    kms_key_id          = aws_kms_key.state[0].arn
    use_lockfile        = true
    allowed_account_ids = [var.target.account_id]
  }
}

output "backend_access_policy_json" {
  description = "Unattached, unverified IAM contract; not a trust policy, identity grant, usable credential or deployment permission."
  value       = local.enabled ? jsonencode(local.backend_access_policy) : null
}
