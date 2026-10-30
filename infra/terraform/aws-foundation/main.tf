locals {
  bucket_arn = "arn:aws:s3:::${var.bucket_name}"
  subnet_numbers = {
    public = 0
    app    = 16
    data   = 32
  }
  subnets = merge([
    for tier, first in local.subnet_numbers : {
      for index, zone in var.availability_zones : "${tier}-${index}" => {
        tier = tier
        zone = zone
        cidr = cidrsubnet(var.vpc_cidr, 8, first + index)
      }
    }
  ]...)
  # Unattached example policy; no user, access key or deployment identity is created.
  report_reader_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListSyntheticReports"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.bucket_arn]
        Condition = {
          StringLike = { "s3:prefix" = ["reports/*"] }
        }
      },
      {
        Sid      = "ReadSyntheticReports"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${local.bucket_arn}/reports/*"]
      },
      {
        Sid      = "DecryptSyntheticReportsViaS3"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [aws_kms_key.artifacts.arn]
        Condition = {
          StringEquals = {
            "kms:ViaService"                   = "s3.${var.region}.amazonaws.com"
            "kms:EncryptionContext:aws:s3:arn" = local.bucket_arn
          }
        }
      }
    ]
  }
  transport_policy = {
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [local.bucket_arn, "${local.bucket_arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  }
}

resource "aws_vpc" "foundation" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = var.project }
}

resource "aws_subnet" "tier" {
  for_each                = local.subnets
  vpc_id                  = aws_vpc.foundation.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.zone
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.project}-${each.key}", Tier = each.value.tier }
}

resource "aws_internet_gateway" "edge" {
  vpc_id = aws_vpc.foundation.id
  tags   = { Name = "${var.project}-edge" }
}

resource "aws_route_table" "tier" {
  for_each = local.subnet_numbers
  vpc_id   = aws_vpc.foundation.id
  tags     = { Name = "${var.project}-${each.key}" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.tier["public"].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.edge.id
}

resource "aws_route_table_association" "tier" {
  for_each       = local.subnets
  subnet_id      = aws_subnet.tier[each.key].id
  route_table_id = aws_route_table.tier[each.value.tier].id
}

# Private app/data tiers intentionally have no Internet/NAT routes in this foundation.
resource "aws_default_security_group" "closed" {
  vpc_id  = aws_vpc.foundation.id
  ingress = []
  egress  = []
  tags    = { Name = "${var.project}-default-deny" }
}

resource "aws_security_group" "application" {
  name_prefix = "${var.project}-app-"
  description = "Application tier; ingress must be explicitly designed before AWS deployment"
  vpc_id      = aws_vpc.foundation.id
  # Standalone vpc_security_group_*_rule resources own rules; never mix inline rules.
}

resource "aws_security_group" "database" {
  name_prefix = "${var.project}-db-"
  description = "PostgreSQL access from the application security group only"
  vpc_id      = aws_vpc.foundation.id
  # Standalone vpc_security_group_*_rule resources own rules; never mix inline rules.
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.application.id
  description                  = "PostgreSQL from application only"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "postgres" {
  security_group_id            = aws_security_group.application.id
  referenced_security_group_id = aws_security_group.database.id
  description                  = "PostgreSQL to database only"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = var.bucket_name
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_kms_key" "artifacts" {
  description             = "Synthetic report artifact encryption; unprovisioned G1 design"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableOnlyTargetAccountIAMDelegation"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.account_id}:root" }
        Action    = "kms:*"
        # In a KMS key policy '*' refers to THIS key, not every key in the account.
        Resource = "*"
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "kms:*"
        Resource  = "*"
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }
    ]
  })
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.artifacts.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_policy" "transport" {
  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode(local.transport_policy)
}

resource "aws_iam_policy" "report_reader" {
  name_prefix = "${var.project}-report-reader-"
  description = "Read-only synthetic reports prefix; deliberately unattached in G1"
  policy      = jsonencode(local.report_reader_policy)
}
