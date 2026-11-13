# The two secrets, as SSM Parameter Store SecureStrings (encrypted with the AWS-managed aws/ssm key).
#
# Terraform creates them with a placeholder through a WRITE-ONLY argument (value_wo): Terraform
# sends it to AWS once and never stores it in its state, and it does not track later changes.
# You set the real values yourself with the AWS CLI after `terraform apply`, so the real secrets
# never appear in .tf files, git or Terraform state. config.py refuses to run while a parameter
# still holds the placeholder.

resource "aws_ssm_parameter" "close_signature_key" {
  name             = "/${local.name}/close_signature_key"
  description      = "Close webhook signature_key (hex), used by the receiver to verify Close-Sig-Hash"
  type             = "SecureString"
  value_wo         = "CHANGE_ME"
  value_wo_version = 1 # bump only to make Terraform write the placeholder again
}

resource "aws_ssm_parameter" "slack_webhook_url" {
  name             = "/${local.name}/slack_webhook_url"
  description      = "Slack incoming webhook URL, used by the processor to send alerts"
  type             = "SecureString"
  value_wo         = "CHANGE_ME"
  value_wo_version = 1 # bump only to make Terraform write the placeholder again
}
