# Alarm: tell a human when a lead ends up in the dead-letter queue (DLQ).
#
# A message reaches the DLQ only after max_receive_count (10) failed deliveries, so the
# DLQ should always be empty. CloudWatch watches its message count; when it is above 0
# the alarm fires and SNS (Simple Notification Service) emails var.alarm_email.
# When the DLQ is empty again, a second "OK" email says the problem is over.

resource "aws_sns_topic" "alarms" {
  name = "${local.name}-alarms"
}

# Only created when an email is given. AWS then sends a "Subscription Confirmation"
# email: click the link in it, or no alarm email is ever delivered.
resource "aws_sns_topic_subscription" "alarm_email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name        = "${local.name}-dlq-not-empty"
  alarm_description = "A lead failed 10 deliveries and is in ${aws_sqs_queue.dlq.name}. Check /aws/lambda/${local.processor_name} logs, then the DLQ."

  namespace   = "AWS/SQS"
  metric_name = "ApproximateNumberOfMessagesVisible" # messages waiting in the DLQ
  dimensions  = { QueueName = aws_sqs_queue.dlq.name }
  statistic   = "Maximum"
  period      = 300 # SQS sends this metric every 5 minutes

  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching" # no data = empty queue = fine

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]
}
