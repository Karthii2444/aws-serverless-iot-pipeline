# Event-Driven Serverless IoT Telemetry Pipeline

[](https://aws.amazon.com/)
[](https://www.terraform.io/)
[](https://www.python.org/)
[License](https://www.google.com/search?q=LICENSE)
[](https://aws.amazon.com/free/)

A production-grade, event-driven IoT data pipeline built entirely on AWS serverless services and provisioned via Terraform. 

The pipeline simulates industrial sensor fleets, ingests telemetry in real time, flags critical equipment anomalies with millisecond latency, decouples reliable data lake archival via queues and dead-letter queues (DLQs), and executes scheduled analytical SQL queries over an Amazon S3 data lake with automated executive reporting.

---

## Architectural Overview

The system implements the **Lambda Architecture** pattern, splitting operational streaming workloads (the "Hot Path") from historical analytical storage (the "Cold Path"):

```text
                     [1. INGESTION]
                     Postman Client
                           │
                           ▼ (HTTP POST / GET)
                [Lambda Function URL]
                           │
                           ▼
               [Lambda 0: IoT Simulator]
                           │
                           ▼ (PutItem / BatchWriteItem)
                 [Amazon DynamoDB]
                           │
═══════════════════════════╪════════════════════════════════════════
                           │ (DynamoDB Streams - CDC)
                           ▼
               [2. REAL-TIME STREAMING]
               [Lambda 1: Stream Detector]
                     │            │
        (If Anomaly) │            │ (If Normal)
                     ▼            ▼
             [Amazon SNS]   [Amazon SQS (Main Queue)]
             (Email Alert)        │
                                  ▼
══════════════════════════════════╪═════════════════════════════════
                                  │
                       [3. STORAGE & RESILIENCE]
                       [Lambda 2: Batch Archiver]
                           │             │
             (Valid Batch) │             │ (Corrupted Payload)
                           ▼             ▼ (After 3 Retries)
                   [Amazon S3 Lake]   [Amazon SQS (DLQ)]
                           │             │
                           ▼             ▼
═══════════════════════════╪═════════════╪══════════════════════════
                           │             ▼
                 [4. SQL ANALYTICS]  [CloudWatch Alarm]
                [Amazon Athena (SQL)]    │
                           ▲             ▼
                           │        [Amazon SNS]
               [Lambda 3: Daily Reporter]
                           ▲
                           │ (Scheduled Cron)
                  [Amazon EventBridge]
                           │
                           ▼
                [Amazon SES (HTML Email)]
```

---

## Data Contract & Database Schema

### DynamoDB Primary Key Design
* **Partition Key (`device_id`)** (`String`): Evenly distributes telemetry traffic across physical DynamoDB storage partitions to avoid hot partitions.
* **Sort Key (`timestamp`)** (`String`): ISO-8601 UTC timestamp string (`YYYY-MM-DDTHH:MM:SSZ`), allowing efficient range queries per machine.

### Telemetry Attribute Schema

| Field Name | Data Type | Example Value | Description & Operational Threshold |
| :--- | :--- | :--- | :--- |
| `device_id` | String | `"sensor-press-001"` | Machine / sensor asset identifier. |
| `timestamp` | String | `"2026-11-05T07:30:00Z"` | ISO-8601 UTC reading timestamp. |
| `telemetry_id` | String | `"9b1deb4d-3b7d-4bad-..."` | Unique UUID for record deduplication. |
| `device_type` | String | `"hydraulic_press"` | Industrial machine category. |
| `temperature_c` | Number (Float) | `68.4` | **Normal**: 50.0–75.0 °C. <br>**Critical Alert**: **> 85.0 °C** (triggers SNS). |
| `vibration_hz` | Number (Float) | `34.2` | **Normal**: 20.0–50.0 Hz. <br>**Critical Alert**: **> 120.0 Hz** (bearing failure risk). |
| `pressure_psi` | Number (Float) | `102.5` | **Normal**: 90.0–110.0 PSI. |
| `battery_pct` | Number (Int) | `94` | Sensor battery charge level (0–100%). |
| `status` | String | `"HEALTHY"` | Operational status (`HEALTHY`, `ANOMALY`, or `ERROR`). |

### Simulated Data Scenarios

```json
// 1. Normal Telemetry (Happy Path -> SQS -> S3 Data Lake)
{
  "device_id": "sensor-press-001",
  "timestamp": "2026-11-05T07:30:00Z",
  "telemetry_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "device_type": "hydraulic_press",
  "temperature_c": 64.2,
  "vibration_hz": 32.1,
  "pressure_psi": 102.4,
  "battery_pct": 95,
  "status": "HEALTHY"
}

// 2. Critical Anomaly (Real-Time SNS Alert Path)
{
  "device_id": "sensor-press-003",
  "timestamp": "2026-11-05T07:30:01Z",
  "telemetry_id": "c4a8d09f-1234-4567-89ab-cdef01234567",
  "device_type": "hydraulic_press",
  "temperature_c": 98.7,
  "vibration_hz": 142.5,
  "pressure_psi": 118.0,
  "battery_pct": 74,
  "status": "ANOMALY"
}

// 3. Deliberate Schema Error (DLQ Test Path)
{
  "device_id": "sensor-press-002",
  "timestamp": "2026-11-05T07:30:02Z",
  "telemetry_id": "e9f01234-5678-90ab-cdef-1234567890ab",
  "device_type": "hydraulic_press",
  "temperature_c": "CORRUPTED_STRING_VALUE",
  "vibration_hz": 40.0,
  "pressure_psi": 100.0,
  "battery_pct": 80,
  "status": "ERROR"
}
```

---

## Lambda Functions Breakdown

| Function | Trigger | Responsibility | Key AWS Permissions |
| :--- | :--- | :--- | :--- |
| **`iot-simulator`** | HTTP (Function URL) | Generates synthetic telemetry, anomalies, and schema errors; writes to DynamoDB. | `dynamodb:PutItem`, `dynamodb:BatchWriteItem` |
| **`iot-stream-detector`** | DynamoDB Streams | Evaluates stream records in sub-second latency; dispatches SNS alerts; forwards to SQS. | `dynamodb:GetRecords`, `sqs:SendMessage`, `sns:Publish` |
| **`iot-batch-archiver`** | SQS (Batch Window) | Validates schema types; writes partitioned JSON to S3; rejects bad records to DLQ. | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `s3:PutObject` |
| **`iot-daily-reporter`** | EventBridge (Daily Cron) | Executes Athena aggregation queries; generates styled HTML; dispatches email via SES. | `athena:StartQueryExecution`, `s3:GetObject`, `ses:SendEmail` |

---

## Postman API Testing Guide

The simulator exposes a public [AWS Lambda Function URL](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html) supporting on-demand invocation:

### Request Format
* **Method**: `POST`
* **URL**: `https://<unique-id>.lambda-url.<region>.on.aws/`
* **Headers**: `Content-Type: application/json`

#### Test Scenario A: Normal Sensor Batch
```json
{
  "count": 25,
  "force_anomaly": false,
  "force_error": false
}
```
* **Expected Result**: 25 records written to DynamoDB, streamed to Lambda 1, forwarded to SQS, and archived to S3.

#### Test Scenario B: Critical Machine Anomaly (SNS Alert)
```json
{
  "count": 10,
  "force_anomaly": true,
  "force_error": false
}
```
* **Expected Result**: An anomaly record (`temp > 92°C`) triggers an immediate email alert to the operator inbox via SNS.

#### Test Scenario C: Corrupted Record (SQS DLQ & CloudWatch Alarm)
```json
{
  "count": 5,
  "force_anomaly": false,
  "force_error": true
}
```
* **Expected Result**: A record with a string temperature value fails Lambda 2 validation, exhausts 3 SQS retries, moves to the DLQ, and fires the CloudWatch alarm.

---

## Repository Structure

```text
aws-serverless-iot-pipeline/
├── .gitignore
├── README.md
├── terraform/
│   ├── main.tf                 # Provider configurations and shared defaults
│   ├── variables.tf            # Region, table name, email variables
│   ├── outputs.tf              # Function URLs, bucket names, and ARNs
│   ├── dynamodb.tf             # DynamoDB table with DynamoDB Streams enabled
│   ├── sqs.tf                  # Main SQS queue and Dead-Letter Queue (DLQ)
│   ├── s3.tf                   # S3 Data Lake and Athena query results bucket
│   ├── sns.tf                  # SNS topic and email subscriptions
│   ├── athena.tf               # Athena database and workgroup
│   ├── iam.tf                  # Least-privilege IAM execution roles
│   └── lambda.tf               # Lambda functions, packaging, and event triggers
├── simulator-lambda/
│   ├── src/lambda_function.py  # Telemetry generator handler
│   └── test/test_simulator.py  # Local unit tests (mocked DynamoDB)
├── detector-lambda/
│   ├── src/lambda_function.py  # Stream evaluation handler
│   └── test/test_detector.py   # Local unit tests (mocked Stream & SNS)
├── archiver-lambda/
│   ├── src/lambda_function.py  # SQS consumer and S3 archiver
│   └── test/test_archiver.py   # Local unit tests (mocked SQS & S3)
└── reporter-lambda/
    ├── src/lambda_function.py  # Athena query runner and SES emailer
    └── test/test_reporter.py   # Local unit tests (mocked Athena & SES)
```

---

## Local Development & Validation (No AWS Account Required)

You can run unit tests and validate Terraform configurations entirely offline:

### 1. Run Unit Tests with Mocked Services
```bash
# Run all unit tests across all Lambda functions
python -m unittest discover -s simulator-lambda/test
```

### 2. Format and Validate Terraform Code
```bash
cd terraform

# Initialize local provider binaries (no account needed)
terraform init

# Check code formatting
terraform fmt -check

# Validate syntax and resource references
terraform validate
```

---

## Deployment & Teardown

### Prerequisites
* [AWS CLI](https://aws.amazon.com/cli/) installed and configured (`aws configure`).
* [Terraform](https://developer.hashicorp.com/terraform) installed (`>= 1.5.0`).

### Deployment
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Teardown
To guarantee zero unexpected AWS charges, destroy all infrastructure with a single command:
```bash
terraform destroy
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.
