output "s3_data_lake_bucket_name" {
  description = "Name of the S3 Data Lake bucket"
  value       = aws_s3_bucket.data_lake.id
}

output "s3_data_lake_bucket_arn" {
  description = "ARN of the S3 Data Lake bucket"
  value       = aws_s3_bucket.data_lake.arn
}