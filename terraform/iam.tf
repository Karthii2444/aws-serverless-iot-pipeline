# ====================================================================
# 1. Simulator Lambda Role (Lambda 0)
# ====================================================================
resource "aws_iam_role" "simulator_role" {
  name = "iot-simulator-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "simulator_basic_logs" {
  role       = aws_iam_role.simulator_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "simulator_dynamodb_write" {
  name = "iot-simulator-dynamodb-write"
  role = aws_iam_role.simulator_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "DynamoDBBatchWrite"
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:BatchWriteItem"]
      Resource = aws_dynamodb_table.iot_telemetry.arn
    }]
  })
}

# ====================================================================
# 2. Stream Detector Lambda Role (Lambda 1)
# ====================================================================
resource "aws_iam_role" "detector_role" {
  name = "iot-detector-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "detector_basic_logs" {
  role       = aws_iam_role.detector_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "detector_permissions" {
  name = "iot-detector-stream-sns-sqs-policy"
  role = aws_iam_role.detector_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadDynamoDBStream"
        Effect = "Allow"
        Action = [
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:DescribeStream",
          "dynamodb:ListStreams"
        ]
        Resource = aws_dynamodb_table.iot_telemetry.stream_arn
      },
      {
        Sid      = "PublishSNSAlert"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.iot_alerts.arn
      },
      {
        Sid      = "ForwardToSQS"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.telemetry_queue.arn
      }
    ]
  })
}

# ====================================================================
# 3. Batch Archiver Lambda Role (Lambda 2)
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

# ====================================================================
# 4. Daily Reporter Lambda Role (Lambda 3)
# ====================================================================
resource "aws_iam_role" "reporter_role" {
  name = "iot-reporter-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "reporter_basic_logs" {
  role       = aws_iam_role.reporter_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "reporter_permissions" {
  name = "iot-reporter-athena-ses-policy"
  role = aws_iam_role.reporter_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AthenaQueryExecution"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3DataLakeAndResultsAccess"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*",
          aws_s3_bucket.athena_results.arn,
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
      },
      {
        Sid      = "GlueCatalogRead"
        Effect   = "Allow"
        Action   = ["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions"]
        Resource = "*"
      },
      {
        Sid      = "SendSESEmail"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      }
    ]
  })
}