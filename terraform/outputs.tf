output "simulator_function_url" {
  description = "Public HTTP endpoint to trigger the simulator from Postman"
  value       = aws_lambda_function_url.simulator_url.function_url
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.iot_telemetry.name
}

output "dynamodb_stream_arn" {
  description = "ARN of the DynamoDB Stream (used for Lambda 1 trigger)"
  value       = aws_dynamodb_table.iot_telemetry.stream_arn
}