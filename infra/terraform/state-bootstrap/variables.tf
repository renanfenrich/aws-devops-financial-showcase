variable "bootstrap_enabled" {
  description = "Resource graph gate only, not deployment authorization. G2-A leaves this false outside mocked tests."
  type        = bool
  default     = false
  nullable    = false
  validation {
    condition     = !var.bootstrap_enabled || var.target != null
    error_message = "Enabling the bootstrap requires an explicit target account, region, bucket and KMS administrator role."
  }
}

variable "target" {
  description = "Explicit future commercial-partition target; null by default. No account/profile or region is discovered. Fixtures are synthetic."
  type = object({
    account_id         = string
    region             = string
    bucket_name        = string
    kms_admin_role_arn = string
  })
  default = null
  validation {
    condition = var.target == null ? true : try(
      can(regex("^[0-9]{12}$", var.target.account_id)) &&
      can(regex("^[a-z]{2}(-[a-z]+)+-[1-9]$", var.target.region)) &&
      !startswith(var.target.region, "cn-") && !startswith(var.target.region, "us-gov-") &&
      !startswith(var.target.region, "us-iso") && !startswith(var.target.region, "eu-iso") &&
      length(var.target.bucket_name) >= 3 && length(var.target.bucket_name) <= 63 &&
      can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.target.bucket_name)) &&
      !startswith(var.target.bucket_name, "xn--") &&
      !startswith(var.target.bucket_name, "sthree-") &&
      !startswith(var.target.bucket_name, "amzn-s3-demo-") &&
      !endswith(var.target.bucket_name, "-s3alias") &&
      !endswith(var.target.bucket_name, "--ol-s3") &&
      !endswith(var.target.bucket_name, "--x-s3") &&
      !endswith(var.target.bucket_name, "--table-s3") &&
      !endswith(var.target.bucket_name, "-an") &&
      can(regex("^arn:aws:iam::${var.target.account_id}:role/([A-Za-z0-9+=,.@_-]+/)*[A-Za-z0-9+=,.@_-]+$", var.target.kms_admin_role_arn)),
      false
    )
    error_message = "Target requires a twelve-digit account, commercial AWS region, valid lowercase bucket name and wildcard-free IAM role ARN in that same account."
  }
}

variable "state_key" {
  description = "One explicit default-workspace state object; no wildcard workspace access or lockfile path is accepted."
  type        = string
  default     = "sandbox/aws-foundation.tfstate"
  nullable    = false
  validation {
    condition = (length(var.state_key) <= 512 &&
      can(regex("^[a-z0-9][a-z0-9/_-]*\\.tfstate$", var.state_key)) &&
    alltrue([for segment in split("/", var.state_key) : length(segment) > 0]))
    error_message = "State key must be a relative lowercase path ending .tfstate, without empty segments, traversal, wildcards or a .tflock suffix."
  }
}
