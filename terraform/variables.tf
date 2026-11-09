variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-south-1"
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

variable "alert_email" {
  description = "Email address to receive SNS critical alerts and SES daily reports"
  type        = string
  default     = "operator@example.com"
}

variable "plant_metadata" {
  description = "Device to facility and maintenance team mapping passed as JSON env var"
  type = map(object({
    plant = string
    team  = string
  }))
  default = {
    "sensor-press-001" = { plant = "Bengaluru-Plant-01", team = "Mechanical-Alpha" }
    "sensor-press-002" = { plant = "Bengaluru-Plant-01", team = "Mechanical-Alpha" }
    "sensor-press-003" = { plant = "Bengaluru-Plant-01", team = "Hydraulics-Beta" }
    "sensor-press-004" = { plant = "Chennai-Plant-02", team = "Hydraulics-Beta" }
    "sensor-press-005" = { plant = "Chennai-Plant-02", team = "Electrical-Gamma" }
  }
}