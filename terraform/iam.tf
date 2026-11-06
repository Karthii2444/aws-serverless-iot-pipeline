# ====================================================================
# 3. IAM Role for Batch Archiver Lambda (Lambda 2)
# ====================================================================
resource "aws_iam_role" "archiver_role" {
  name = "iot-archiver-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "archiver_basic_logs" {
  role       = aws_iam_role.archiver_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "archiver_permissions" {
  name = "iot-archiver-sqs-s3-policy"
  role = aws_iam_role.archiver_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ConsumeSQSQueue"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.telemetry_queue.arn
      },
      {
        Sid      = "WriteToS3DataLake"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:PutObjectTagging"]
        Resource = "${aws_s3_bucket.data_lake.arn}/*"
      }
    ]
  })
}