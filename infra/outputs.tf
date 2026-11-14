# Printed after `terraform apply` (and any time with `terraform output`).

output "webhook_url" {
  description = "Give this URL to Azmat/Ninad for the Close webhook subscription."
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/crm"
}

output "bucket_name" {
  value = aws_s3_bucket.leads.bucket
}

output "delay_queue_url" {
  value = aws_sqs_queue.delay.url
}

output "dlq_url" {
  description = "Messages that failed 10 times. Should stay empty."
  value       = aws_sqs_queue.dlq.url
}

output "set_secrets" {
  description = "Run these yourself to store the real secrets (they are typed, not echoed or saved in history)."
  value       = <<-EOT
    # Slack incoming webhook URL:
    read -rs SECRET && aws ssm put-parameter --region ${var.region} --name ${aws_ssm_parameter.slack_webhook_url.name} --type SecureString --overwrite --value "$SECRET"; unset SECRET

    # Close signature_key (when Azmat/Ninad give it to you):
    read -rs SECRET && aws ssm put-parameter --region ${var.region} --name ${aws_ssm_parameter.close_signature_key.name} --type SecureString --overwrite --value "$SECRET"; unset SECRET
  EOT
}

output "alarm_topic_arn" {
  description = "SNS topic for alarms. If alarm_email is set, confirm the subscription email AWS sends you."
  value       = aws_sns_topic.alarms.arn
}
