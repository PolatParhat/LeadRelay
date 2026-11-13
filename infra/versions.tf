# Which Terraform and which provider versions this code is written for.
terraform {
  required_version = ">= 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # any 6.x, never a 7.x with breaking changes
    }
    archive = {
      source  = "hashicorp/archive" # zips the Lambda code
      version = "~> 2.7"
    }
  }

  # State is kept locally in infra/terraform.tfstate (git-ignored).
  # One person, one environment: a remote S3 backend is not needed yet.
}
