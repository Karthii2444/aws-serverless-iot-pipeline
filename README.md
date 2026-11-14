# Event-Driven Serverless IoT Telemetry Pipeline

[](https://aws.amazon.com/)
[](https://www.terraform.io/)
[](https://www.python.org/)
[License](https://www.google.com/search?q=LICENSE)
[](https://aws.amazon.com/free/)

A production-grade, event-driven IoT data pipeline built entirely on AWS serverless services and provisioned via Terraform. 

The pipeline simulates industrial sensor fleets, ingests telemetry in real time via an authenticated API Gateway (`x-api-key`), computes a composite **Machine Health Index (MHI)** with sub-second latency, dispatches structured on-call incident tickets via Amazon SNS, decouples multi-prefix data lake archival via Amazon SQS with **Partial Batch Response (`ReportBatchItemFailures`)** and Dead-Letter Queues (DLQs), writes Athena-optimized Newline-Delimited JSON (NDJSON) into hourly Hive-partitioned S3 storage, archives permanent PDF executive summaries into S3 (`reports/`), and executes scheduled analytical SQL queries across dual Amazon Athena tables (`telemetry` and `incidents`) with automated MIME email delivery via Amazon SES.

---

## Architectural Overview

The system implements the **Lambda Architecture** pattern, splitting operational streaming workloads (the "Hot Path") from historical multi-table analytical storage (the "Cold Path"):

```text
                     [1. INGESTION]
                     Postman Client
                           │
                           ▼ (HTTP POST with x-api-key)
                [Amazon API Gateway REST API]
                           │ (Usage Plan & Rate Limiting)
                           ▼
               [Lambda 0: IoT Simulator]
                           │
                           ▼ (PutItem / BatchWriteItem with Decimal types)
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
                                          ▼ (Batch of up to 10 messages)
══════════════════════════════════════════╪═════════════════════════
                                          │
                               [3. STORAGE & RESILIENCE]
                               [Lambda 2: Batch Archiver]
                                   │                │
                     (Valid Batch) │                │ (ReportBatchItemFailures)
                                   ▼                ▼ (Only Bad Message Retried)
                         [Amazon S3 Data Lake]   [Amazon SQS (DLQ)]
                          ├── telemetry/            │
                          ├── incidents/            ▼
                          └── reports/ (PDFs)   [CloudWatch Alarm]
                                   │                │
═══════════════════════════════════╪═══════════[Amazon SNS]
                                   │
                         [4. SQL ANALYTICS]
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
                   [Amazon SES (HTML Body + Attached PDF)]
```

---

## Architecture & Design Decisions

### 1. API Gateway with `x-api-key` vs. Public Function URLs
* **Enterprise Ingress Security**: In production, external ingestion endpoints must not be exposed unauthenticated to the public internet. The simulator is protected by an [Amazon API Gateway](https://aws.amazon.com/api-gateway/) REST API that enforces mandatory `x-api-key` header authentication and a managed Usage Plan (10 req/sec rate limit, 20 burst limit, 1,000 monthly quota).

### 2. DynamoDB Streams vs. Amazon Kinesis
* **The Problem**: [Amazon Kinesis Data Streams](https://aws.amazon.com/kinesis/data-streams/) does not offer an ongoing free tier and bills ~$0.015 per shard-hour (~$11/month) even when completely idle.
* **The Solution**: [Amazon DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html) is built on the same underlying sharded stream technology as Kinesis. When AWS Lambda reads from DynamoDB Streams, it uses the identical shard-iterator polling model (`GetRecords`), providing true event-driven Change Data Capture (CDC) with 2.5 million read stream request units free per month.

### 3. Partial Batch Response (`ReportBatchItemFailures`)
* **Preventing Duplicate Writes**: By default, if a single message in an SQS batch fails, standard Lambda behavior retries the *entire* batch, creating duplicate records in S3 for the valid messages.
* **The Solution**: Lambda 2 implements `batchItemFailures`. It writes valid messages cleanly to S3 and returns only the corrupted message ID back to SQS. SQS acknowledges the good records and retries *only* the corrupted message until it exhausts 3 retries and lands in the Dead-Letter Queue (DLQ).

### 4. Multi-Domain S3 Partitioning (`telemetry/`, `incidents/`, `reports/`)
* **Domain Separation**: Lambda 2 writes all validated records to `s3://<bucket>/telemetry/` and routes flagged anomalies (`CRITICAL` and `WARNING`) to a dedicated `s3://<bucket>/incidents/` prefix in Newline-Delimited JSON (NDJSON).
* **Permanent Executive PDF Storage**: Lambda 3 compiles daily vector PDFs and stores them under `s3://<bucket>/reports/year=YYYY/month=MM/` while simultaneously streaming them as MIME attachments via SES.
* **Query Optimization**: [Amazon Athena](https://aws.amazon.com/athena/) registers two distinct external tables (`iot_telemetry_db.telemetry` and `iot_telemetry_db.incidents`). Querying historical incidents scans only the lightweight `incidents/` prefix rather than scanning millions of normal sensor readings.

---

## Data Contract & Database Schema

### 1. Raw Telemetry Schema (DynamoDB `iot-telemetry`)
* **Partition Key (`device_id`)** (`String`): Evenly distributes telemetry traffic across physical DynamoDB storage partitions.
* **Sort Key (`timestamp`)** (`String`): ISO-8601 UTC timestamp string (`YYYY-MM-DDTHH:MM:SSZ`).

| Field Name | Data Type | Example Value | Description & Operational Threshold |
| :--- | :--- | :--- | :--- |
| `device_id` | String | `"sensor-press-001"` | Machine / sensor asset identifier. |
| `timestamp` | String | `"2026-11-09T08:00:00Z"` | ISO-8601 UTC reading timestamp. |
| `telemetry_id` | String | `"9b1deb4d-3b7d-4bad-..."` | Unique UUID for record deduplication. |
| `device_type` | String | `"hydraulic_press"` | Industrial machine category. |
| `temperature_c` | Number (Decimal) | `68.4` | **Normal**: 50.0–75.0 °C. **Warning**: > 78.0 °C. **Critical**: **> 85.0 °C**. |
| `vibration_hz` | Number (Decimal) | `34.2` | **Normal**: 20.0–50.0 Hz. **Warning**: > 80.0 Hz. **Critical**: **> 120.0 Hz**. |
| `pressure_psi` | Number (Decimal) | `102.5` | **Normal**: 90.0–110.0 PSI. **Abnormal**: < 85.0 or > 115.0 PSI. |
| `battery_pct` | Number (Int) | `94` | Sensor battery charge level (Warning < 25%). |
| `status` | String | `"HEALTHY"` | Simulator status flag (`HEALTHY`, `ANOMALY`, or `ERROR`). |

### 2. Enriched Payload Schema (Added by Lambda 1)

| Enriched Field | Data Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `health_score` | Number (Int) | `25` | Composite score (100 = optimal; deductions for temp, vibration, pressure, battery). |
| `severity` | String | `"CRITICAL"` | Classification: `NORMAL` (80–100), `WARNING` (50–79), `CRITICAL` (< 50), or `UNVALIDATED`. |
| `is_incident` | Boolean | `true` | `true` if `severity` is `WARNING` or `CRITICAL` (routes copy to `s3://.../incidents/`). |
| `anomaly_reasons` | List[String] | `["CRITICAL_OVERHEAT", ...]` | Specific threshold violations triggered by the reading. |
| `plant_location` | String | `"Bengaluru-Plant-01"` | Enriched facility identifier from environment configuration. |
| `maintenance_team`| String | `"Mechanical-Alpha"` | Assigned on-call engineering team. |
| `evaluated_at` | String | `"2026-11-09T08:00:01Z"` | UTC timestamp when stream inspection completed. |

---

## Real-Time Incident Alert Format (Amazon SNS)

When Lambda 1 detects a `CRITICAL` or `WARNING` event, it immediately publishes a structured on-call ticket to [Amazon SNS](https://aws.amazon.com/sns/):

```text
Subject: [CRITICAL ALERT] IoT Machine Fault | sensor-press-005 (Health: 5/100)

====================================================================
                 🚨 INDUSTRIAL IOT INCIDENT TICKET 🚨
====================================================================

INCIDENT SUMMARY
--------------------------------------------------------------------
Severity Level   : CRITICAL
Health Score     : 5 / 100
Incident ID      : b0baa2f2-a4d4-4ea7-91f6-f62e5ffce002
Detected At      : 2026-11-09T06:03:31Z

ASSET METADATA
--------------------------------------------------------------------
Device ID        : sensor-press-005
Equipment Type   : hydraulic_press
Facility         : Chennai-Plant-02
Assigned Team    : Electrical-Gamma

TELEMETRY DIAGNOSTICS
--------------------------------------------------------------------
* Temperature    : 102.72 C   [MAX LIMIT: 85.0 C]
* Vibration      : 134.81 Hz  [MAX LIMIT: 120.0 Hz]
* Pressure       : 125.9 PSI  [NORMAL RANGE: 85.0 - 115.0 PSI]
* Battery Level  : 63 %

TRIGGERED VIOLATIONS
--------------------------------------------------------------------
1. CRITICAL_OVERHEAT: Temperature (102.72 C) exceeded 85.0 C limit.
2. SEVERE_VIBRATION: Vibration (134.81 Hz) exceeded 120.0 Hz limit.
3. PRESSURE_VARIANCE: Pressure (125.9 PSI) outside 85-115 PSI band.

RECOMMENDED ACTION
--------------------------------------------------------------------
Immediate inspection required on sensor-press-005. High risk of 
thermal seizure or hydraulic seal failure.
====================================================================
```

---

## Lambda Functions Breakdown

| Function | Source Directory | Trigger | Responsibility | Key AWS Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **`iot-simulator`** | `simulator-lambda/src/` | API Gateway (`POST /simulate`) | Generates synthetic telemetry with randomized anomalies and errors; writes to DynamoDB via Decimal types. | `dynamodb:PutItem`, `dynamodb:BatchWriteItem` |
| **`iot-stream-detector`** | `detector-lambda/src/` | DynamoDB Streams | Unmarshals stream records; calculates Health Score; enriches metadata; fires SNS alerts; forwards to SQS. | `dynamodb:GetRecords`, `sqs:SendMessage`, `sns:Publish` |
| **`iot-batch-archiver`** | `archiver-lambda/src/` | SQS (Batch Window) | Enforces schema validation with `batchItemFailures`; writes NDJSON to hourly Hive partitions in S3 (`telemetry/` & `incidents/`). | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `s3:PutObject` |
| **`iot-daily-reporter`** | `reporter-lambda/src/` | EventBridge (Cron) | Queries both Athena tables (`telemetry` & `incidents`); archives PDF to S3 `reports/`; sends HTML + PDF via SES. | `athena:StartQueryExecution`, `s3:GetObject`, `s3:PutObject`, `ses:SendRawEmail` |

---

## API Testing Guide (cURL & Postman)

### Request Format
* **Method**: `POST`
* **URL**: `https://<api-id>.execute-api.<region>.amazonaws.com/dev/simulate`
* **Headers**:
  * `Content-Type: application/json`
  * `x-api-key: <your-api-key>`

```bash
curl --location 'https://<api-id>.execute-api.ap-south-1.amazonaws.com/dev/simulate' \
--header 'Content-Type: application/json' \
--header 'x-api-key: YOUR_API_KEY' \
--data '{
  "count": 20,
  "force_anomaly": true,
  "force_error": true
}'
```

---

## Repository Structure

```text
aws-serverless-iot-pipeline/
├── .gitignore
├── README.md
├── requirements-dev.txt        # Local testing dependencies (boto3, fpdf2)
├── terraform/
│   ├── main.tf                 # Provider configurations and default tags
│   ├── variables.tf            # Region, table name, email variables
│   ├── outputs.tf              # API Gateway URL, API key, bucket names, and ARNs
│   ├── api_gateway.tf          # REST API, API key, usage plan, and throttling
│   ├── dynamodb.tf             # DynamoDB table with DynamoDB Streams enabled
│   ├── sqs.tf                  # Main SQS queue and Dead-Letter Queue (DLQ)
│   ├── s3.tf                   # S3 Data Lake and Athena query results bucket
│   ├── sns.tf                  # SNS topic and email subscriptions
│   ├── athena.tf               # Athena database, workgroup, and lifecycle rules
│   ├── monitoring.tf           # CloudWatch Alarm on SQS DLQ
│   ├── iam.tf                  # Least-privilege IAM execution roles
│   └── lambda.tf               # Lambda functions, packaging, and event triggers
├── simulator-lambda/
│   ├── src/main.py             # Telemetry generator handler (Decimal types)
│   └── test/test_simulator.py  # Local unit tests (mocked DynamoDB)
├── detector-lambda/
│   ├── src/
│   │   ├── main.py             # Stream controller and orchestration
│   │   ├── evaluator.py        # Health scoring & threshold engine
│   │   └── templates.py        # SNS incident ticket templates
│   └── test/test_detector.py   # Local unit tests (mocked Stream, SNS & SQS)
├── archiver-lambda/
│   ├── src/
│   │   ├── main.py             # SQS batch controller with batchItemFailures
│   │   ├── validator.py        # Strict schema validator
│   │   └── s3_writer.py        # NDJSON formatter & hourly Hive S3 writer
│   └── test/test_archiver.py   # Local unit tests (mocked SQS & S3)
└── reporter-lambda/
    ├── src/
    │   ├── main.py             # Dual-table Athena runner & SES emailer
    │   ├── athena_client.py    # Asynchronous Athena query execution & polling
    │   ├── email_template.py   # Styled HTML executive dashboard
    │   └── pdf_generator.py    # Vector PDF compiler with FPDF2
    └── test/test_reporter.py   # Local unit tests (mocked Athena, S3 & SES)
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

### 2. Run All Unit Test Suites
```bash
python -m unittest discover -s simulator-lambda/test
python -m unittest discover -s detector-lambda/test
python -m unittest discover -s archiver-lambda/test
python -m unittest discover -s reporter-lambda/test
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

## Athena Table Setup

The Athena **database**, **workgroup**, and both **external tables** (`telemetry` and `incidents`) are fully provisioned by Terraform via the AWS Glue Data Catalog — no manual steps in the query editor are required.

After `terraform apply`, the following are ready to query immediately:

| Resource | Name |
| :--- | :--- |
| Athena Database | `iot_telemetry_db` |
| Athena Workgroup | `iot-analytics-workgroup` |
| Table (all readings) | `iot_telemetry_db.telemetry` → `s3://<bucket>/telemetry/` |
| Table (anomalies only) | `iot_telemetry_db.incidents` → `s3://<bucket>/incidents/` |

### Loading Partitions After Data Arrives

The Archiver Lambda writes data into Hive-partitioned S3 paths (`year=/month=/day=/hour=`). After the first batch of telemetry flows through the pipeline, run the following once in the **Athena Query Editor** to register the new partitions:

```sql
MSCK REPAIR TABLE iot_telemetry_db.telemetry;
MSCK REPAIR TABLE iot_telemetry_db.incidents;
```

> **Note:** Re-run `MSCK REPAIR TABLE` whenever new date or hour partitions are created (e.g., the following day). This is required for the Reporter Lambda's partition-pruned queries (`WHERE year = ... AND month = ... AND day = ...`) to return correct results.

### Verify End-to-End with a Test Query

Open the **Athena Query Editor**, select workgroup `iot-analytics-workgroup` and database `iot_telemetry_db`, then run:

```sql
SELECT device_id, severity, health_score, evaluated_at
FROM iot_telemetry_db.telemetry
ORDER BY evaluated_at DESC
LIMIT 10;
```

If rows are returned, the full pipeline is working end-to-end. ✅

---

## License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.