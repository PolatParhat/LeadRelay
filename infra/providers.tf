# The AWS provider: how Terraform talks to AWS.
provider "aws" {
  region = var.region # always us-east-1, whatever your AWS CLI default is

  # Added to every resource Terraform creates, so they are easy to find (and bill).
  default_tags {
    tags = {
      Project   = "LeadRelay"
      ManagedBy = "Terraform"
    }
  }
}

# Facts about the account we are logged in to (read-only).
data "aws_caller_identity" "current" {}

locals {
  name        = "leadrelay"
  account_id  = data.aws_caller_identity.current.account_id
  bucket_name = "${local.name}-${local.account_id}" # e.g. leadrelay-123456789012

  receiver_name  = "${local.name}-receiver"
  processor_name = "${local.name}-processor"
}
