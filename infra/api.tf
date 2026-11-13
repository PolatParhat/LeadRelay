# The public webhook URL: API Gateway HTTP API -> receiver Lambda.
# Close will POST every lead event to  https://<api-id>.execute-api.us-east-1.amazonaws.com/crm

resource "aws_apigatewayv2_api" "webhook" {
  name          = "${local.name}-webhook"
  protocol_type = "HTTP"
}

# How API Gateway calls the receiver. Payload format 1.0 = the event shape in the requirements
# (headers, body as a JSON string, isBase64Encoded), which receiver.py expects.
resource "aws_apigatewayv2_integration" "receiver" {
  api_id                 = aws_apigatewayv2_api.webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.receiver.invoke_arn
  payload_format_version = "1.0"
  timeout_milliseconds   = 12000 # a bit above the receiver's 10 s, below Close's 15 s
}

# Only POST /crm exists. Any other method or path gets 404 from API Gateway, without
# ever starting the Lambda.
resource "aws_apigatewayv2_route" "crm" {
  api_id    = aws_apigatewayv2_api.webhook.id
  route_key = "POST /crm"
  target    = "integrations/${aws_apigatewayv2_integration.receiver.id}"
}

# One stage, deployed automatically on every change, with a request limit and access logs.
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.webhook.id
  name        = "$default"
  auto_deploy = true

  # Protects the Lambda (and your bill) from floods: Close sends far fewer than this.
  default_route_settings {
    throttling_rate_limit  = 20 # requests per second, on average
    throttling_burst_limit = 50 # short bursts allowed above that
  }

  # One JSON line per request: who called, status code, latency. Useful to debug 401/400s.
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId = "$context.requestId"
      time      = "$context.requestTime"
      ip        = "$context.identity.sourceIp"
      route     = "$context.routeKey"
      status    = "$context.status"
      latencyMs = "$context.responseLatency"
      error     = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.name}-webhook"
  retention_in_days = var.log_retention_days
}

# Allow API Gateway (only this API, only POST /crm) to call the receiver.
resource "aws_lambda_permission" "api_invokes_receiver" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.receiver.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.webhook.execution_arn}/*/POST/crm"
}
