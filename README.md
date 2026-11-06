# Event-Driven Serverless IoT Telemetry Pipeline

[](https://aws.amazon.com/)
[](https://www.terraform.io/)
[](https://www.python.org/)
[License](https://www.google.com/search?q=LICENSE)
[](https://aws.amazon.com/free/)

A production-grade, event-driven IoT data pipeline built entirely on AWS serverless services and provisioned via Terraform. 

The pipeline simulates industrial sensor fleets, ingests telemetry in real time, computes a composite **Machine Health Index (MHI)** with sub-second latency, dispatches structured on-call incident tickets via Amazon SNS, decouples multi-prefix data lake archival via Amazon SQS and Dead-Letter Queues (DLQs), and executes scheduled analytical SQL queries across dual Amazon Athena tables (`telemetry` and `incidents`) with automated HTML executive reporting via Amazon SES.

---

## Architectural Overview

The system implements the **Lambda Architecture** pattern, splitting operational streaming workloads (the "Hot Path") from historical multi-table analytical storage (the "Cold Path"):

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
             [2. REAL-TIME STREAM ENRICHMENT]
             [Lambda 1: Stream Detector & Scorer]
              (Health Scoring & Metadata Enrichment)
                     │                    │
       (If Incident) │                    │ (All Enriched Records)
                     ▼                    ▼
             [Amazon SNS]         [Amazon SQS (Main Queue)]
       (Incident Ticket Email)            │
                                          ▼
══════════════════════════════════════════╪═════════════════════════
                                          │
                               [3. STORAGE & RESILIENCE]
                               [Lambda 2: Batch Archiver]
                                   │                │
                     (Valid Batch) │                │ (Corrupted Payload)
                                   ▼                ▼ (After 3 Retries)
                         [Amazon S3 Data Lake]   [Amazon SQS (DLQ)]
                          ├── telemetry/            │
                          └── incidents/            ▼
                                   │        [CloudWatch Alarm]
                                   ▼                │
═══════════════════════════════════╪════════════════╪═══════════════
                                   │                ▼
                         [4. SQL ANALYTICS]   [Amazon SNS]
                        [Amazon Athena (SQL)]
                         ├── Table: telemetry
                         └── Table: incidents
                                   ▲
                                   │ (Queries Both Tables)
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

### 1. Raw Telemetry Schema (DynamoDB `iot-telemetry`)
* **Partition Key (`device_id`)** (`String`): Evenly distributes telemetry traffic across physical DynamoDB storage partitions.
* **Sort Key (`timestamp`)** (`String`): ISO-8601 UTC timestamp string (`YYYY-MM-DDTHH:MM:SSZ`).

| Field Name | Data Type | Example Value | Description & Operational Threshold |
| :--- | :--- | :--- | :--- |
| `device_id` | String | `"sensor-press-001"` | Machine / sensor asset identifier. |
| `timestamp` | String | `"2026-11-06T08:00:00Z"` | ISO-8601 UTC reading timestamp. |
| `telemetry_id` | String | `"9b1deb4d-3b7d-4bad-..."` | Unique UUID for record deduplication. |
| `device_type` | String | `"hydraulic_press"` | Industrial machine category. |
| `temperature_c` | Number (Float) | `68.4` | **Normal**: 50.0–75.0 °C. **Warning**: > 78.0 °C. **Critical**: **> 85.0 °C**. |
| `vibration_hz` | Number (Float) | `34.2` | **Normal**: 20.0–50.0 Hz. **Warning**: > 80.0 Hz. **Critical**: **> 120.0 Hz**. |
| `pressure_psi` | Number (Float) | `102.5` | **Normal**: 90.0–110.0 PSI. **Abnormal**: < 85.0 or > 115.0 PSI. |
| `battery_pct` | Number (Int) | `94` | Sensor battery charge level (Warning < 25%). |
| `status` | String | `"HEALTHY"` | Simulator status flag (`HEALTHY`, `ANOMALY`, or `ERROR`). |

### 2. Enriched Payload & Incident Schema (Added by Lambda 1)

Lambda 1 computes a composite **Machine Health Score (0–100)** and enriches each record with operational metadata before forwarding to SQS:

| Enriched Field | Data Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `health_score` | Number (Int) | `25` | Composite score (100 = optimal; deductions for temp, vibration, pressure, battery). |
| `severity` | String | `"CRITICAL"` | Classification: `NORMAL` (80–100), `WARNING` (50–79), `CRITICAL` (< 50), or `UNVALIDATED`. |
| `is_incident` | Boolean | `true` | `true` if `severity` is `WARNING` or `CRITICAL` (routes copy to `s3://.../incidents/`). |
| `anomaly_reasons` | List[String] | `["CRITICAL_OVERHEAT", ...]` | Specific threshold violations triggered by the reading. |
| `plant_location` | String | `"Bengaluru-Plant-01"` | Enriched facility identifier based on device mapping. |
| `maintenance_team`| String | `"Mechanical-Alpha"` | Assigned on-call engineering team. |
| `evaluated_at` | String | `"2026-11-06T08:00:01Z"` | UTC timestamp when stream inspection completed. |

---

## Real-Time Incident Alert Format (Amazon SNS)

When Lambda 1 detects a `CRITICAL` or `WARNING` event, it immediately publishes a structured on-call ticket to [Amazon SNS](https://aws.amazon.com/sns/):

```text
Subject: [CRITICAL ALERT] IoT Machine Fault | sensor-press-003 (Health: 25/100)

====================================================================
                 🚨 INDUSTRIAL IOT INCIDENT TICKET 🚨
====================================================================

INCIDENT SUMMARY
--------------------------------------------------------------------
Severity Level   : CRITICAL
Health Score     : 25 / 100
Incident ID      : c4a8d09f-1234-4567-89ab-cdef01234567
Detected At      : 2026-11-06T08:00:01Z

ASSET METADATA
--------------------------------------------------------------------
Device ID        : sensor-press-003
Equipment Type   : hydraulic_press
Facility         : Bengaluru-Plant-01
Assigned Team    : Mechanical-Alpha

TELEMETRY DIAGNOSTICS
--------------------------------------------------------------------
* Temperature    : 98.7 °C    [MAX LIMIT: 85.0 °C]
* Vibration      : 142.5 Hz   [MAX LIMIT: 120.0 Hz]
* Pressure       : 118.0 PSI  [NORMAL RANGE: 90.0 - 110.0 PSI]
* Battery Level  : 74 %

TRIGGERED VIOLATIONS
--------------------------------------------------------------------
1. CRITICAL_OVERHEAT: Temperature (98.7 °C) exceeded 85.0 °C limit.
2. SEVERE_VIBRATION: Vibration (142.5 Hz) exceeded 120.0 Hz limit.
3. HIGH_PRESSURE_VARIANCE: Pressure (118.0 PSI) outside 85-115 PSI band.

RECOMMENDED ACTION
--------------------------------------------------------------------
Immediate inspection required on sensor-press-003. High risk of 
thermal seizure or hydraulic seal failure.
====================================================================
```

---

## Lambda Functions Breakdown

| Function | Source File | Trigger | Responsibility | Key AWS Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **`iot-simulator`** | `simulator-lambda/src/main.py` | HTTP (Function URL) | Generates synthetic telemetry with randomized anomalies and errors; writes to DynamoDB. | `dynamodb:PutItem`, `dynamodb:BatchWriteItem` |
| **`iot-stream-detector`** | `detector-lambda/src/main.py` | DynamoDB Streams | Unmarshals stream records; calculates Health Score; enriches metadata; fires SNS alerts; forwards to SQS. | `dynamodb:GetRecords`, `sqs:SendMessage`, `sns:Publish` |
| **`iot-batch-archiver`** | `archiver-lambda/src/main.py` | SQS (Batch Window) | Validates schema types; writes valid records to `telemetry/` and incidents to `incidents/`; rejects errors to DLQ. | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `s3:PutObject` |
| **`iot-daily-reporter`** | `reporter-lambda/src/main.py` | EventBridge (Cron) | Queries both Athena tables (`telemetry` & `incidents`); sends HTML summary + incident log via SES. | `athena:StartQueryExecution`, `s3:GetObject`, `ses:SendEmail` |

---

## Postman API Testing Guide

### Request Format
* **Method**: `POST`
* **URL**: `https://<unique-id>.lambda-url.<region>.on.aws/`
* **Headers**: `Content-Type: application/json`

#### Test Scenario A: Normal Sensor Batch
```json
{
  "count": 20,
  "force_anomaly": false,
  "force_error": false
}
```
* **Expected Result**: 20 records written to DynamoDB, scored as `NORMAL` by Lambda 1, queued in SQS, and archived to `s3://<bucket>/telemetry/`.

#### Test Scenario B: Randomized Machine Anomalies (SNS Alert + Incident Partition)
```json
{
  "count": 20,
  "force_anomaly": true,
  "force_error": false
}
```
* **Expected Result**: 2 to 3 random anomalies are injected across the batch. Lambda 1 scores them as `CRITICAL`, dispatches SNS incident ticket emails, and flags `is_incident = true` so Lambda 2 archives them into both `telemetry/` and `incidents/`.

#### Test Scenario C: Corrupted Record (SQS DLQ & CloudWatch Alarm)
```json
{
  "count": 20,
  "force_anomaly": false,
  "force_error": true
}
```
* **Expected Result**: 2 to 3 records with corrupted string temperatures pass through Lambda 1 as `UNVALIDATED` so the stream never blocks, then fail strict schema validation in Lambda 2, exhaust 3 SQS retries, land in the Dead-Letter Queue, and trigger a CloudWatch alarm.

---

## Repository Structure

```text
aws-serverless-iot-pipeline/
├── .gitignore
├── README.md
├── requirements-dev.txt        # Local testing dependencies (boto3)
├── terraform/
│   ├── main.tf                 # Provider configurations and default tags
│   ├── variables.tf            # Region, table name, email variables
│   ├── outputs.tf              # Function URLs, bucket names, and ARNs
│   ├── dynamodb.tf             # DynamoDB table with DynamoDB Streams enabled
│   ├── sqs.tf                  # Main SQS queue and Dead-Letter Queue (DLQ)
│   ├── s3.tf                   # S3 Data Lake and Athena query results bucket
│   ├── sns.tf                  # SNS topic and email subscriptions
│   ├── athena.tf               # Athena database and dual table definitions
│   ├── iam.tf                  # Least-privilege IAM execution roles
│   └── lambda.tf               # Lambda functions, packaging, and event triggers
├── simulator-lambda/
│   ├── src/main.py             # Telemetry generator handler
│   └── test/test_simulator.py  # Local unit tests (mocked DynamoDB)
├── detector-lambda/
│   ├── src/main.py             # Stream enrichment & health scoring handler
│   └── test/test_detector.py   # Local unit tests (mocked Stream, SNS & SQS)
├── archiver-lambda/
│   ├── src/main.py             # Dual-folder S3 archiver & schema validator
│   └── test/test_archiver.py   # Local unit tests (mocked SQS & S3)
└── reporter-lambda/
    ├── src/main.py             # Dual-table Athena runner & SES HTML emailer
    └── test/test_reporter.py   # Local unit tests (mocked Athena & SES)
```

---

## Local Development & Validation (No AWS Account Required)

### 1. Set Up Virtual Environment
```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Git Bash / Linux / macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. Run Unit Tests Offline
```bash
python -m unittest discover -s simulator-lambda/test
python -m unittest discover -s detector-lambda/test
```

### 3. Validate Terraform Configurations
```bash
cd terraform
terraform init
terraform fmt -check
terraform validate
```

---

## Deployment & Teardown

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
