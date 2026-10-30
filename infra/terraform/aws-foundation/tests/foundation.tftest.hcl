# The only provider in this suite is mocked: never supply AWS credentials.
mock_provider "aws" {}

run "secure_foundation" {
  command = plan
  assert {
    condition     = length(aws_subnet.tier) == 6 && length(distinct([for subnet in aws_subnet.tier : subnet.cidr_block])) == 6
    error_message = "The design requires six non-overlapping /24 subnets across three tiers and two AZs."
  }
  assert {
    condition     = length(distinct([for subnet in aws_subnet.tier : subnet.availability_zone])) == 2 && alltrue([for subnet in aws_subnet.tier : !subnet.map_public_ip_on_launch])
    error_message = "Exactly two AZs and no automatically allocated public addresses are required."
  }
  assert {
    condition     = keys(aws_route_table.tier) == ["app", "data", "public"] && aws_route.public_internet.destination_cidr_block == "0.0.0.0/0"
    error_message = "Route tables must isolate three tiers and permit an Internet default route only in public."
  }
  assert {
    condition     = length(aws_default_security_group.closed.ingress) == 0 && length(aws_default_security_group.closed.egress) == 0
    error_message = "The default security group must deny ingress and egress."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.postgres.from_port == 5432 && aws_vpc_security_group_ingress_rule.postgres.to_port == 5432 && aws_vpc_security_group_ingress_rule.postgres.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.postgres.cidr_ipv6 == null
    error_message = "Database access must be PostgreSQL from a referenced security group, never a CIDR."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.artifacts.block_public_acls && aws_s3_bucket_public_access_block.artifacts.block_public_policy && aws_s3_bucket_public_access_block.artifacts.ignore_public_acls && aws_s3_bucket_public_access_block.artifacts.restrict_public_buckets
    error_message = "Every S3 public access control must be enabled."
  }
  assert {
    condition     = one(aws_s3_bucket_ownership_controls.artifacts.rule).object_ownership == "BucketOwnerEnforced" && one(aws_s3_bucket_versioning.artifacts.versioning_configuration).status == "Enabled" && !aws_s3_bucket.artifacts.force_destroy
    error_message = "ACLs must be disabled, versioning enabled and forced deletion disabled."
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.artifacts.rule).apply_server_side_encryption_by_default).sse_algorithm == "aws:kms"
    error_message = "Customer-managed KMS encryption is required."
  }
  assert {
    condition     = aws_kms_key.artifacts.enable_key_rotation && aws_kms_key.artifacts.deletion_window_in_days == 30 && jsondecode(aws_kms_key.artifacts.policy).Statement[0].Principal.AWS == "arn:aws:iam::${var.account_id}:root" && jsondecode(aws_kms_key.artifacts.policy).Statement[1].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "The artifact CMK must rotate, allow a recovery window and scope delegation to the target account over TLS."
  }
  assert {
    condition     = output.report_reader_policy.Statement[2].Action == ["kms:Decrypt"] && output.report_reader_policy.Statement[2].Condition.StringEquals["kms:ViaService"] == "s3.${var.region}.amazonaws.com" && output.report_reader_policy.Statement[2].Condition.StringEquals["kms:EncryptionContext:aws:s3:arn"] == "arn:aws:s3:::${var.bucket_name}"
    error_message = "Decrypt permission must be scoped to this bucket through S3 only."
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.transport.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false" && jsondecode(aws_s3_bucket_policy.transport.policy).Statement[0].Effect == "Deny"
    error_message = "The bucket policy must explicitly deny insecure transport."
  }
  assert {
    condition     = output.report_reader_policy.Statement[0].Action == ["s3:ListBucket"] && output.report_reader_policy.Statement[0].Condition.StringLike["s3:prefix"] == ["reports/*"] && output.report_reader_policy.Statement[1].Action == ["s3:GetObject"] && output.report_reader_policy.Statement[1].Resource == ["arn:aws:s3:::${var.bucket_name}/reports/*"]
    error_message = "Report access must remain read-only and prefix-scoped."
  }
}

run "reject_public_vpc" {
  command = plan
  variables { vpc_cidr = "8.8.0.0/16" }
  expect_failures = [var.vpc_cidr]
}

run "reject_malformed_cidr" {
  command = plan
  variables { vpc_cidr = "not-a-cidr" }
  expect_failures = [var.vpc_cidr]
}

run "reject_duplicate_az" {
  command = plan
  variables { availability_zones = ["us-east-1a", "us-east-1a"] }
  expect_failures = [var.availability_zones]
}

run "reject_wrong_region_az" {
  command = plan
  variables { availability_zones = ["eu-west-1a", "eu-west-1b"] }
  expect_failures = [var.availability_zones]
}

run "reject_invalid_bucket" {
  command = plan
  variables { bucket_name = "PUBLIC_BUCKET" }
  expect_failures = [var.bucket_name]
}

run "reject_noncanonical_cidr" {
  command = plan
  variables { vpc_cidr = "10.42.1.0/16" }
  expect_failures = [var.vpc_cidr]
}

run "reject_invalid_account" {
  command = plan
  variables { account_id = "not-an-account" }
  expect_failures = [var.account_id]
}
