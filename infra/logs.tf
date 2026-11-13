# One CloudWatch log group per Lambda. Created by Terraform (not by Lambda on first run) so
# retention is set and `terraform destroy` removes them too.

resource "aws_cloudwatch_log_group" "receiver" {
  name              = "/aws/lambda/${local.receiver_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "processor" {
  name              = "/aws/lambda/${local.processor_name}"
  retention_in_days = var.log_retention_days
}
