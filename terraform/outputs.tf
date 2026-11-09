output "s3_data_lake_bucket_name" {
  description = "Name of the S3 Data Lake bucket"
  value       = aws_s3_bucket.data_lake.id
}

output "s3_data_lake_bucket_arn" {
  description = "ARN of the S3 Data Lake bucket"
  value       = aws_s3_bucket.data_lake.arn
}

output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = "${aws_api_gateway_stage.dev.invoke_url}/simulate"
}

output "api_gateway_api_key" {
  description = "API Key required in x-api-key header"
  value       = aws_api_gateway_api_key.simulator_key.value
  sensitive   = true
}