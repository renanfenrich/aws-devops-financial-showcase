output "subnet_layout" {
  description = "Deterministic tier/AZ/CIDR design; does not attest deployed AWS resources."
  value       = local.subnets
}

output "report_reader_policy" {
  description = "Unattached read-only IAM policy scoped to reports/*."
  value       = local.report_reader_policy
}

output "transport_policy" {
  description = "Explicit denial of non-TLS S3 access."
  value       = local.transport_policy
}
