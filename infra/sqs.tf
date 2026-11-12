# The 10-minute wait: S3 tells SQS about every new source/ file, SQS hides the message for
# delay_seconds, then hands it to the processor Lambda.

# Dead-letter queue (DLQ): where a message goes after max_receive_count failed deliveries,
# so a human can look at it. Kept 14 days (the SQS maximum).
resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name}-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true    # encrypted at rest, free
}

# The delay queue.
resource "aws_sqs_queue" "delay" {
  name                       = "${local.name}-delay"
  delay_seconds              = var.delay_seconds       # 600: every new message is invisible for 10 min
  visibility_timeout_seconds = var.retry_after_seconds # 300: a failed message returns 5 min later
  message_retention_seconds  = 345600                  # 4 days, far more than the ~1 h of retries
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count # 10
  })

  lifecycle {
    precondition {
      condition     = var.max_receive_count > var.owner_max_tries
      error_message = "max_receive_count must be above owner_max_tries, or 'owner missing' leads land in the DLQ."
    }
  }
}

# Only our delay queue may send messages to the DLQ.
resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.delay.arn]
  })
}

# Allow S3 to put messages on the delay queue, but only for OUR bucket in OUR account.
resource "aws_sqs_queue_policy" "delay" {
  queue_url = aws_sqs_queue.delay.id
  policy    = data.aws_iam_policy_document.delay_queue.json
}

data "aws_iam_policy_document" "delay_queue" {
  statement {
    sid       = "AllowS3FromOurBucket"
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.delay.arn]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.leads.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# The S3 event notification: every new .json file under source/ -> one SQS message.
resource "aws_s3_bucket_notification" "source_to_delay" {
  bucket = aws_s3_bucket.leads.id

  queue {
    queue_arn     = aws_sqs_queue.delay.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "source/"
    filter_suffix = ".json"
  }

  # S3 checks it may send to the queue when the notification is created.
  depends_on = [aws_sqs_queue_policy.delay]
}
