# Dead-Letter Queue (DLQ) for isolating corrupted payloads
resource "aws_sqs_queue" "telemetry_dlq" {
  name                      = "iot-telemetry-dlq"
  message_retention_seconds = 1209600 # 14 days max retention
}

# Main Telemetry Queue with Redrive Policy to DLQ after 3 retries
resource "aws_sqs_queue" "telemetry_queue" {
  name                       = "iot-telemetry-queue"
  visibility_timeout_seconds = 180 # 6x Lambda timeout (30s)
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.telemetry_dlq.arn
    maxReceiveCount     = 3
  })
}