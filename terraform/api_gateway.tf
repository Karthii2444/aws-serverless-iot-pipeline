# 1. REST API Definition
resource "aws_api_gateway_rest_api" "simulator_api" {
  name        = "iot-simulator-api"
  description = "REST API Gateway for triggering IoT Telemetry Simulator with API Key auth"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# 2. Resource Path: /simulate
resource "aws_api_gateway_resource" "simulate" {
  rest_api_id = aws_api_gateway_rest_api.simulator_api.id
  parent_id   = aws_api_gateway_rest_api.simulator_api.root_resource_id
  path_part   = "simulate"
}

# 3. Method: POST (Enforces API Key requirement)
resource "aws_api_gateway_method" "post_simulate" {
  rest_api_id      = aws_api_gateway_rest_api.simulator_api.id
  resource_id     = aws_api_gateway_resource.simulate.id
  http_method     = "POST"
  authorization   = "NONE"
  api_key_required = true
}

# 4. Lambda Proxy Integration
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.simulator_api.id
  resource_id            = aws_api_gateway_resource.simulate.id
  http_method            = aws_api_gateway_method.post_simulate.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.simulator.invoke_arn
}

# 5. API Deployment
resource "aws_api_gateway_deployment" "simulator_deployment" {
  rest_api_id = aws_api_gateway_rest_api.simulator_api.id

  depends_on = [
    aws_api_gateway_integration.lambda_integration,
    aws_api_gateway_method.post_simulate
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# 6. Stage: dev
resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.simulator_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.simulator_api.id
  stage_name    = "dev"
}

# 7. Generate API Key
resource "aws_api_gateway_api_key" "simulator_key" {
  name        = "iot-simulator-key"
  description = "API Key for Postman invocation of IoT Simulator"
  enabled     = true
}

# 8. Usage Plan (Throttling & Quota Guardrail)
resource "aws_api_gateway_usage_plan" "simulator_plan" {
  name        = "iot-simulator-usage-plan"
  description = "Throttling and quota guardrail for IoT Simulator"

  api_stages {
    api_id = aws_api_gateway_rest_api.simulator_api.id
    stage  = aws_api_gateway_stage.dev.stage_name
  }

  throttle_settings {
    burst_limit = 20
    rate_limit  = 10
  }

  quota_settings {
    limit  = 1000
    period = "MONTH"
  }
}

# 9. Link API Key to Usage Plan
resource "aws_api_gateway_usage_plan_key" "simulator_plan_key" {
  key_id        = aws_api_gateway_api_key.simulator_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.simulator_plan.id
}

# 10. Lambda Permission to Allow API Gateway Invocation
resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.simulator.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.simulator_api.execution_arn}/*/*"
}