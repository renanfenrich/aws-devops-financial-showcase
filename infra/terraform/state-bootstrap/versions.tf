terraform {
  required_version = "= 1.17.1"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.71.0"
    }
  }
}

# No backend, credential, identity-discovery data source or remote state is used.
# Offline gates use a mock provider. When disabled, the real provider must not
# validate credentials, request the account ID, or contact instance metadata.
provider "aws" {
  region                      = var.target == null ? null : var.target.region
  allowed_account_ids         = var.target == null ? null : [var.target.account_id]
  skip_credentials_validation = !var.bootstrap_enabled
  skip_requesting_account_id  = !var.bootstrap_enabled
  skip_metadata_api_check     = !var.bootstrap_enabled
  skip_region_validation      = !var.bootstrap_enabled
  default_tags {
    tags = {
      Project   = "financial-showcase"
      Purpose   = "terraform-state"
      ManagedBy = "terraform"
    }
  }
}
