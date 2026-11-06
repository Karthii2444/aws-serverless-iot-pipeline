# S3 Bucket for storing Athena query execution results
resource "aws_s3_bucket" "athena_results" {
  bucket = "iot-athena-query-results-${random_string.bucket_suffix.result}"

  tags = {
    Name = "iot-athena-query-results"
  }
}

# Auto-delete query results older than 2 days to stay safely in Free Tier
resource "aws_s3_bucket_lifecycle_configuration" "athena_results_lifecycle" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "clean-old-query-results"
    status = "Enabled"

    filter {}

    expiration {
      days = 2
    }
  }
}

# Athena Database
resource "aws_athena_database" "iot_db" {
  name   = "iot_telemetry_db"
  bucket = aws_s3_bucket.athena_results.id
}

# Athena Workgroup with enforced output location
resource "aws_athena_workgroup" "iot_workgroup" {
  name = "iot-analytics-workgroup"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/output/"
    }
  }
}