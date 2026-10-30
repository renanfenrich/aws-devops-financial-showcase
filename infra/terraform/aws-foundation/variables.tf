variable "project" {
  description = "Short lowercase resource prefix."
  type        = string
  default     = "financial-showcase"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project))
    error_message = "Project must be 3-31 lowercase letters, numbers or hyphens, starting with a letter."
  }
}

variable "region" {
  description = "Illustrative AWS region; no AWS API is called by mocked tests."
  type        = string
  default     = "us-east-1"
  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[1-9]$", var.region))
    error_message = "Region must use AWS region syntax."
  }
}

variable "availability_zones" {
  description = "Exactly two distinct AZs in region, explicit to avoid discovery API calls."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
  validation {
    condition = length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2 && alltrue([
      for zone in var.availability_zones : can(regex("^${var.region}[a-z]$", zone))
    ])
    error_message = "Provide two distinct availability zones belonging to region."
  }
}

variable "vpc_cidr" {
  description = "Private RFC1918 IPv4 /16; deterministic /24 subnets are derived from it."
  type        = string
  default     = "10.42.0.0/16"
  validation {
    condition = try(cidrhost(var.vpc_cidr, 0) == split("/", var.vpc_cidr)[0], false) && can(cidrnetmask(var.vpc_cidr)) && can(regex("/16$", var.vpc_cidr)) && can(regex(
      "^(10\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.)", var.vpc_cidr
    ))
    error_message = "VPC must be an RFC1918 IPv4 /16."
  }
}

variable "bucket_name" {
  description = "Illustrative globally unique artifact bucket name, never created in G1."
  type        = string
  default     = "financial-showcase-synthetic-artifacts-example"
  validation {
    condition = length(var.bucket_name) >= 3 && length(var.bucket_name) <= 63 && can(regex(
      "^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.bucket_name
    )) && !can(regex("^[0-9]+-[0-9]+-[0-9]+-[0-9]+$", var.bucket_name))
    error_message = "Bucket must be 3-63 lowercase letters, numbers and hyphens, with alphanumeric ends."
  }
}

variable "account_id" {
  description = "Illustrative account for a scoped KMS key policy; verify the actual target before any future deployment."
  type        = string
  default     = "111122223333"
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Account ID must contain exactly twelve digits."
  }
}
