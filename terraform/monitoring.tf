# CloudWatch Alarm: Alerts when any corrupted message enters the DLQ
resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
  alarm_name          = "iot-telemetry-dlq-messages-detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alarm triggers when corrupted telemetry messages fail retries and enter the DLQ."

  dimensions = {
    QueueName = aws_sqs_queue.telemetry_dlq.name
  }

  alarm_actions = [aws_sns_topic.iot_alerts.arn]

  tags = {
    Name = "iot-telemetry-dlq-alarm"
  }
}