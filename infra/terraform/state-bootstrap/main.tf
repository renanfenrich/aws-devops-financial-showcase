locals {
  enabled    = var.bootstrap_enabled && var.target != null
  bucket_arn = var.target == null ? null : "arn:aws:s3:::${var.target.bucket_name}"
  state_arn  = var.target == null ? null : "${local.bucket_arn}/${var.state_key}"
  lock_arn   = var.target == null ? null : "${local.state_arn}.tflock"

  # IAM JSON contract only: no policy, role, principal, attachment or trust grant
  # is created. A future reviewed workload identity must be selected separately.
  backend_access_policy = !local.enabled ? null : {
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListOnlyStatePrefix"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [local.bucket_arn]
        Condition = {
          StringEquals = { "s3:prefix" = [var.state_key] }
        }
      },
      {
        Sid      = "ReadWriteOnlyState"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = [local.state_arn]
      },
      {
        Sid      = "ManageOnlyNativeLock"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [local.lock_arn]
      },
      {
        Sid      = "UseStateKeyOnlyThroughThisBucket"
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [aws_kms_key.state[0].arn]
        Condition = {
          StringEquals = {
            "kms:CallerAccount"                = var.target.account_id
            "kms:ViaService"                   = "s3.${var.target.region}.amazonaws.com"
            "kms:EncryptionContext:aws:s3:arn" = local.bucket_arn
          }
        }
      }
    ]
  }
}

resource "aws_s3_bucket" "state" {
  count         = local.enabled ? 1 : 0
  bucket        = var.target.bucket_name
  force_destroy = false
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_public_access_block" "state" {
  count                   = local.enabled ? 1 : 0
  bucket                  = aws_s3_bucket.state[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "state" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  versioning_configuration { status = "Enabled" }
}

resource "aws_kms_key" "state" {
  count                   = local.enabled ? 1 : 0
  description             = "Dedicated Terraform state encryption; unprovisioned G2-A design"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  multi_region            = false
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableOnlyTargetAccountIAMDelegation"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.target.account_id}:root" }
        Action    = "kms:*"
        # In a key policy this wildcard addresses THIS key, not every account key.
        Resource = "*"
      },
      {
        Sid       = "ExplicitKeyAdministrator"
        Effect    = "Allow"
        Principal = { AWS = var.target.kms_admin_role_arn }
        Action = [
          "kms:DescribeKey", "kms:GetKeyPolicy", "kms:PutKeyPolicy",
          "kms:EnableKeyRotation", "kms:DisableKeyRotation", "kms:GetKeyRotationStatus",
          "kms:UpdateKeyDescription", "kms:TagResource", "kms:UntagResource",
          "kms:ListResourceTags", "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
          "kms:EnableKey", "kms:DisableKey"
        ]
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
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state[0].arn
    }
    bucket_key_enabled       = true
    blocked_encryption_types = ["SSE-C"]
  }
}

resource "aws_s3_bucket_policy" "state" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [local.bucket_arn, "${local.bucket_arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "RequireKMSUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${local.bucket_arn}/*"
        Condition = { StringNotEquals = { "s3:x-amz-server-side-encryption" = "aws:kms" } }
      },
      {
        Sid       = "RequireThisStateKey"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${local.bucket_arn}/*"
        Condition = { StringNotEquals = { "s3:x-amz-server-side-encryption-aws-kms-key-id" = aws_kms_key.state[0].arn } }
      }
    ]
  })
}
