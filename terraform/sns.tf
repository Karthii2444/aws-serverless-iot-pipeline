resource "aws_sns_topic" "iot_alerts" {
  name = "iot-critical-alerts"
}

resource "aws_sns_topic_subscription" "alert_email" {
  topic_arn = aws_sns_topic.iot_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}