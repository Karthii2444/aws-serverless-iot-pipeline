# Execution Role for Simulator Lambda
resource "aws_iam_role" "simulator_role" {
  name = "iot-simulator-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# CloudWatch Logs Basic Execution
resource "aws_iam_role_policy_attachment" "simulator_basic_logs" {
  role       = aws_iam_role.simulator_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Least-Privilege DynamoDB Write Policy
resource "aws_iam_role_policy" "simulator_dynamodb_write" {
  name = "iot-simulator-dynamodb-write"
  role = aws_iam_role.simulator_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBBatchWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = aws_dynamodb_table.iot_telemetry.arn
      }
    ]
  })
}