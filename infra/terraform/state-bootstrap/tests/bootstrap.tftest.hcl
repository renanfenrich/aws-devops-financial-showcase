# Every enabled graph below is synthetic and uses the mock provider only.
mock_provider "aws" {
  override_during = plan
  mock_resource "aws_kms_key" {
    defaults = {
      arn = "arn:aws:kms:us-east-1:111122223333:key/00000000-1111-2222-3333-444444444444"
    }
  }
}

variables {
  bootstrap_enabled = true
  target = {
    account_id         = "111122223333"
    region             = "us-east-1"
    bucket_name        = "financial-showcase-offline-state-fixture"
    kms_admin_role_arn = "arn:aws:iam::111122223333:role/fixture-state-administrator"
  }
}

run "disabled_defaults" {
  command = plan
  variables {
    bootstrap_enabled = false
    target            = null
  }
  assert {
    condition     = length(aws_s3_bucket.state) == 0 && length(aws_kms_key.state) == 0 && length(aws_s3_bucket_public_access_block.state) == 0 && length(aws_s3_bucket_ownership_controls.state) == 0 && length(aws_s3_bucket_versioning.state) == 0 && length(aws_s3_bucket_server_side_encryption_configuration.state) == 0 && length(aws_s3_bucket_policy.state) == 0
    error_message = "The default gate must produce no AWS resource instances."
  }
  assert {
    condition     = output.backend_config == null && output.backend_access_policy_json == null
    error_message = "Disabled mode must not emit a usable backend or access-policy contract."
  }
}

run "disabled_even_with_target" {
  command = plan
  variables { bootstrap_enabled = false }
  assert {
    condition     = length(aws_s3_bucket.state) == 0 && length(aws_kms_key.state) == 0 && output.backend_config == null && output.backend_access_policy_json == null
    error_message = "Supplying an explicit target cannot activate the graph."
  }
}

run "secure_state_graph" {
  command = plan
  assert {
    condition     = length(aws_s3_bucket.state) == 1 && length(aws_kms_key.state) == 1 && !aws_s3_bucket.state[0].force_destroy
    error_message = "An enabled mock requires one dedicated bucket and one key; no forced bucket deletion."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.state[0].block_public_acls && aws_s3_bucket_public_access_block.state[0].block_public_policy && aws_s3_bucket_public_access_block.state[0].ignore_public_acls && aws_s3_bucket_public_access_block.state[0].restrict_public_buckets
    error_message = "All four public-access controls are required."
  }
  assert {
    condition     = one(aws_s3_bucket_ownership_controls.state[0].rule).object_ownership == "BucketOwnerEnforced" && one(aws_s3_bucket_versioning.state[0].versioning_configuration).status == "Enabled"
    error_message = "State requires disabled ACLs and version recovery."
  }
  assert {
    condition     = aws_kms_key.state[0].enable_key_rotation && aws_kms_key.state[0].deletion_window_in_days == 30 && !aws_kms_key.state[0].multi_region
    error_message = "The dedicated regional KMS key must rotate and retain a 30-day recovery window."
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.state[0].rule).apply_server_side_encryption_by_default).sse_algorithm == "aws:kms" && one(one(aws_s3_bucket_server_side_encryption_configuration.state[0].rule).apply_server_side_encryption_by_default).kms_master_key_id == aws_kms_key.state[0].arn && one(aws_s3_bucket_server_side_encryption_configuration.state[0].rule).bucket_key_enabled && toset(one(aws_s3_bucket_server_side_encryption_configuration.state[0].rule).blocked_encryption_types) == toset(["SSE-C"])
    error_message = "Default encryption must use this CMK, enable bucket keys and block SSE-C."
  }
  assert {
    condition     = jsondecode(aws_kms_key.state[0].policy).Statement[0].Principal.AWS == "arn:aws:iam::111122223333:root" && jsondecode(aws_kms_key.state[0].policy).Statement[1].Principal.AWS == var.target.kms_admin_role_arn && !contains(jsondecode(aws_kms_key.state[0].policy).Statement[1].Action, "kms:Decrypt")
    error_message = "Key management must identify the explicit target-account role and not imply cryptographic use."
  }
  assert {
    condition     = alltrue([for statement in jsondecode(aws_s3_bucket_policy.state[0].policy).Statement : statement.Effect == "Deny"]) && jsondecode(aws_s3_bucket_policy.state[0].policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false" && jsondecode(aws_s3_bucket_policy.state[0].policy).Statement[1].Condition.StringNotEquals["s3:x-amz-server-side-encryption"] == "aws:kms" && jsondecode(aws_s3_bucket_policy.state[0].policy).Statement[2].Condition.StringNotEquals["s3:x-amz-server-side-encryption-aws-kms-key-id"] == aws_kms_key.state[0].arn
    error_message = "The bucket policy must deny insecure transport and writes that do not specify this KMS key."
  }
}

run "backend_and_iam_contract" {
  command = plan
  assert {
    condition     = output.backend_config.bucket == var.target.bucket_name && output.backend_config.key == "sandbox/aws-foundation.tfstate" && output.backend_config.region == var.target.region && output.backend_config.encrypt && output.backend_config.kms_key_id == aws_kms_key.state[0].arn && output.backend_config.use_lockfile && output.backend_config.allowed_account_ids == [var.target.account_id] && toset(keys(output.backend_config)) == toset(["bucket", "key", "region", "encrypt", "kms_key_id", "use_lockfile", "allowed_account_ids"])
    error_message = "The backend contract must use native locking, the selected CMK/account, and contain no credentials or DynamoDB options."
  }
  assert {
    condition     = length(jsondecode(output.backend_access_policy_json).Statement) == 4 && jsondecode(output.backend_access_policy_json).Statement[0].Action == ["s3:ListBucket"] && jsondecode(output.backend_access_policy_json).Statement[0].Resource == ["arn:aws:s3:::${var.target.bucket_name}"] && jsondecode(output.backend_access_policy_json).Statement[0].Condition.StringEquals["s3:prefix"] == [var.state_key]
    error_message = "List access must be restricted to the exact bucket/state prefix."
  }
  assert {
    condition     = toset(jsondecode(output.backend_access_policy_json).Statement[1].Action) == toset(["s3:GetObject", "s3:PutObject"]) && jsondecode(output.backend_access_policy_json).Statement[1].Resource == ["arn:aws:s3:::${var.target.bucket_name}/${var.state_key}"] && toset(jsondecode(output.backend_access_policy_json).Statement[2].Action) == toset(["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]) && jsondecode(output.backend_access_policy_json).Statement[2].Resource == ["arn:aws:s3:::${var.target.bucket_name}/${var.state_key}.tflock"]
    error_message = "Only the lock object may be deleted; state must retain exact Get/Put permissions."
  }
  assert {
    condition     = toset(jsondecode(output.backend_access_policy_json).Statement[3].Action) == toset(["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]) && jsondecode(output.backend_access_policy_json).Statement[3].Resource == [aws_kms_key.state[0].arn] && jsondecode(output.backend_access_policy_json).Statement[3].Condition.StringEquals["kms:CallerAccount"] == var.target.account_id && jsondecode(output.backend_access_policy_json).Statement[3].Condition.StringEquals["kms:ViaService"] == "s3.${var.target.region}.amazonaws.com" && jsondecode(output.backend_access_policy_json).Statement[3].Condition.StringEquals["kms:EncryptionContext:aws:s3:arn"] == "arn:aws:s3:::${var.target.bucket_name}"
    error_message = "KMS use must be scoped to this key, account and bucket through regional S3."
  }
  assert {
    condition     = alltrue([for statement in jsondecode(output.backend_access_policy_json).Statement : statement.Effect == "Allow" && !contains(statement.Resource, "*") && !can(statement.Principal)])
    error_message = "An identity-policy contract must not introduce wildcard resources, a Principal or a trust grant."
  }
}

run "alternate_state_key_is_scoped" {
  command = plan
  variables { state_key = "sandbox/eks-runtime.tfstate" }
  assert {
    condition     = output.backend_config.key == "sandbox/eks-runtime.tfstate" && jsondecode(output.backend_access_policy_json).Statement[1].Resource == ["arn:aws:s3:::${var.target.bucket_name}/sandbox/eks-runtime.tfstate"] && jsondecode(output.backend_access_policy_json).Statement[2].Resource == ["arn:aws:s3:::${var.target.bucket_name}/sandbox/eks-runtime.tfstate.tflock"]
    error_message = "Changing a state key must also rescope state and lock permissions."
  }
}

run "reject_enabled_without_target" {
  command = plan
  variables { target = null }
  expect_failures = [var.bootstrap_enabled]
}

run "reject_invalid_account" {
  command = plan
  variables { target = merge(var.target, { account_id = "not-an-account" }) }
  expect_failures = [var.target]
}

run "reject_cross_account_administrator" {
  command = plan
  variables { target = merge(var.target, { kms_admin_role_arn = "arn:aws:iam::444455556666:role/administrator" }) }
  expect_failures = [var.target]
}

run "reject_wildcard_administrator" {
  command = plan
  variables { target = merge(var.target, { kms_admin_role_arn = "arn:aws:iam::111122223333:role/*" }) }
  expect_failures = [var.target]
}

run "reject_user_administrator" {
  command = plan
  variables { target = merge(var.target, { kms_admin_role_arn = "arn:aws:iam::111122223333:user/administrator" }) }
  expect_failures = [var.target]
}

run "reject_noncommercial_region" {
  command = plan
  variables { target = merge(var.target, { region = "us-gov-west-1" }) }
  expect_failures = [var.target]
}

run "reject_invalid_bucket" {
  command = plan
  variables { target = merge(var.target, { bucket_name = "State_Bucket" }) }
  expect_failures = [var.target]
}

run "reject_account_regional_namespace_name" {
  command = plan
  variables { target = merge(var.target, { bucket_name = "fixture-state-111122223333-us-east-1-an" }) }
  expect_failures = [var.target]
}

run "reject_isolated_region" {
  command = plan
  variables { target = merge(var.target, { region = "us-iso-east-1" }) }
  expect_failures = [var.target]
}

run "reject_isolated_b_region" {
  command = plan
  variables { target = merge(var.target, { region = "us-isob-east-1" }) }
  expect_failures = [var.target]
}

run "reject_isolated_e_region" {
  command = plan
  variables { target = merge(var.target, { region = "eu-isoe-west-1" }) }
  expect_failures = [var.target]
}

run "reject_empty_role_basename" {
  command = plan
  variables { target = merge(var.target, { kms_admin_role_arn = "arn:aws:iam::111122223333:role//" }) }
  expect_failures = [var.target]
}

run "reject_trailing_role_path" {
  command = plan
  variables { target = merge(var.target, { kms_admin_role_arn = "arn:aws:iam::111122223333:role/platform/" }) }
  expect_failures = [var.target]
}

run "accept_named_role_under_path" {
  command = plan
  variables { target = merge(var.target, { kms_admin_role_arn = "arn:aws:iam::111122223333:role/platform/state-administrator" }) }
  assert {
    condition     = jsondecode(aws_kms_key.state[0].policy).Statement[1].Principal.AWS == var.target.kms_admin_role_arn
    error_message = "An explicit named role under an IAM path must remain usable in the contract."
  }
}

run "reject_absolute_key" {
  command = plan
  variables { state_key = "/sandbox/state.tfstate" }
  expect_failures = [var.state_key]
}

run "reject_traversal_key" {
  command = plan
  variables { state_key = "sandbox/../other/state.tfstate" }
  expect_failures = [var.state_key]
}

run "reject_wildcard_key" {
  command = plan
  variables { state_key = "sandbox/*/state.tfstate" }
  expect_failures = [var.state_key]
}

run "reject_empty_path_segment" {
  command = plan
  variables { state_key = "sandbox//state.tfstate" }
  expect_failures = [var.state_key]
}

run "reject_lockfile_as_state_key" {
  command = plan
  variables { state_key = "sandbox/state.tfstate.tflock" }
  expect_failures = [var.state_key]
}
