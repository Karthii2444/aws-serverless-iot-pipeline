variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "dynamodb_table_name" {
  description = "DynamoDB table for IoT telemetry"
  type        = string
  default     = "iot-telemetry"
}