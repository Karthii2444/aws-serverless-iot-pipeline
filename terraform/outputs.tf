output "simulator_function_url" {
  description = "Public HTTP endpoint to trigger the simulator from Postman"
  value       = aws_lambda_function_url.simulator_url.function_url
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.iot_telemetry.name
}

output "dynamodb_stream_arn" {
  description = "ARN of the DynamoDB Stream"
  value       = aws_dynamodb_table.iot_telemetry.stream_arn
}

output "sns_alerts_topic_arn" {
  description = "ARN of the SNS Topic for critical alerts"
  value       = aws_sns_topic.iot_alerts.arn
}

output "sqs_main_queue_url" {
  description = "URL of the main SQS telemetry queue"
  value       = aws_sqs_queue.telemetry_queue.id
}

output "sqs_dlq_url" {
  description = "URL of the SQS Dead-Letter Queue"
  value       = aws_sqs_queue.telemetry_dlq.id
}