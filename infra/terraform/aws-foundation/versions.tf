terraform {
  required_version = "= 1.17.1"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.71.0"
    }
  }
}

# No backend or credentials are configured in G1. Only mocked tests are supported.
provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = var.project
      Environment = "showcase"
      ManagedBy   = "terraform"
      DataClass   = "synthetic"
    }
  }
}
