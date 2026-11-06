resource "aws_dynamodb_table" "iot_telemetry" {
  name           = var.dynamodb_table_name
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5

  hash_key  = "device_id"
  range_key = "timestamp"

  attribute {
    name = "device_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # DynamoDB Streams enabled (New Image view type)
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

  tags = {
    Name = var.dynamodb_table_name
  }
}