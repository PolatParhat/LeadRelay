# What each Lambda may do: exactly what its code needs, nothing more (least privilege).

# Both roles can be taken on ("assumed") only by the Lambda service.
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------- receiver

resource "aws_iam_role" "receiver" {
  name               = local.receiver_name
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "receiver" {
  name   = "${local.receiver_name}-permissions"
  role   = aws_iam_role.receiver.id
  policy = data.aws_iam_policy_document.receiver.json
}

data "aws_iam_policy_document" "receiver" {
  statement {
    sid       = "WriteRawEvents"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.leads.arn}/source/*"]
  }
  statement {
    sid       = "ReadSignatureKey"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.close_signature_key.arn]
  }
  statement {
    sid       = "WriteLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.receiver.arn}:*"]
  }
}

# ---------------------------------------------------------------- processor

resource "aws_iam_role" "processor" {
  name               = local.processor_name
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "processor" {
  name   = "${local.processor_name}-permissions"
  role   = aws_iam_role.processor.id
  policy = data.aws_iam_policy_document.processor.json
}

data "aws_iam_policy_document" "processor" {
  statement {
    sid       = "ReadRawEvents"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.leads.arn}/source/*"]
  }
  statement {
    sid       = "WriteEnriched"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.leads.arn}/target/*"]
  }
  statement {
    sid       = "AlertMarkers"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.leads.arn}/alerts_sent/*"]
  }
  statement {
    # Without ListBucket, S3 answers 403 AccessDenied (not 404 NoSuchKey) for a missing file,
    # and read_marker() could not tell "no marker yet" from "not allowed".
    sid       = "TellMissingFromForbidden"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.leads.arn]
  }
  statement {
    sid       = "ReadSlackUrl"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.slack_webhook_url.arn]
  }
  statement {
    sid       = "ConsumeDelayQueue"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.delay.arn]
  }
  statement {
    sid       = "WriteLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.processor.arn}:*"]
  }
}
