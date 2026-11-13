# The two Lambda functions. Both run the same zip (our src/leadrelay package);
# each points at a different handler function inside it.

# Zip src/ -> infra/build/leadrelay.zip. The zip holds leadrelay/*.py at its root, so the
# handler "leadrelay.receiver.handler" means: file leadrelay/receiver.py, function handler().
# Only the standard library + boto3 are used, and the Lambda runtime already has boto3,
# so nothing else goes in the zip.
data "archive_file" "code" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/leadrelay.zip"
  excludes    = ["leadrelay/__pycache__", "leadrelay/__pycache__/**"]
}

locals {
  lambda_runtime = "python3.13"
  lambda_arch    = ["arm64"] # Graviton: cheaper than x86, and our code is pure Python
}

# ---------------------------------------------------------------- receiver

resource "aws_lambda_function" "receiver" {
  function_name    = local.receiver_name
  role             = aws_iam_role.receiver.arn
  runtime          = local.lambda_runtime
  architectures    = local.lambda_arch
  handler          = "leadrelay.receiver.handler"
  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256 # new code -> new deploy
  timeout          = 10                                         # Close waits at most 15 s
  memory_size      = 256

  environment {
    variables = {
      BUCKET_NAME         = aws_s3_bucket.leads.bucket
      SIGNATURE_KEY_PARAM = aws_ssm_parameter.close_signature_key.name
    }
  }

  logging_config {
    log_format            = "JSON" # logging extra={...} fields become searchable JSON keys
    log_group             = aws_cloudwatch_log_group.receiver.name
    application_log_level = "INFO"
    system_log_level      = "WARN"
  }

  depends_on = [aws_iam_role_policy.receiver]
}

# ---------------------------------------------------------------- processor

resource "aws_lambda_function" "processor" {
  function_name    = local.processor_name
  role             = aws_iam_role.processor.arn
  runtime          = local.lambda_runtime
  architectures    = local.lambda_arch
  handler          = "leadrelay.processor.handler"
  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256
  timeout          = 30 # lookup (max ~18 s) + S3 + Slack; well under the 300 s visibility timeout
  memory_size      = 256

  environment {
    variables = {
      BUCKET_NAME         = aws_s3_bucket.leads.bucket
      OWNER_MAX_TRIES     = tostring(var.owner_max_tries)
      SLACK_WEBHOOK_PARAM = aws_ssm_parameter.slack_webhook_url.name
    }
  }

  logging_config {
    log_format            = "JSON"
    log_group             = aws_cloudwatch_log_group.processor.name
    application_log_level = "INFO"
    system_log_level      = "WARN"
  }

  depends_on = [aws_iam_role_policy.processor]
}

# The queue -> processor connection. Lambda polls the queue for us and calls the
# processor with one message at a time.
resource "aws_lambda_event_source_mapping" "delay_to_processor" {
  event_source_arn        = aws_sqs_queue.delay.arn
  function_name           = aws_lambda_function.processor.arn
  batch_size              = 1                           # one lead per call
  function_response_types = ["ReportBatchItemFailures"] # processor returns batchItemFailures
}
