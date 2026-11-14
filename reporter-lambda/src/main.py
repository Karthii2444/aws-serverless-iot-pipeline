import os
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import boto3

from athena_client import execute_athena_query
from email_template import render_executive_report_html
from pdf_generator import generate_pdf_report

logger = logging.getLogger("iot-daily-reporter")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

athena_client = boto3.client("athena")
ses_client = boto3.client("ses")
s3_client = boto3.client("s3")

ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE", "iot_telemetry_db")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "iot-analytics-workgroup")
DATA_LAKE_BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "")


def send_email_with_pdf_attachment(sender, receiver, subject, html_body, pdf_bytes, filename):
    """Packages and sends a MIME multipart email with an attached PDF via Amazon SES."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    # 1. HTML Body
    msg_body = MIMEMultipart("alternative")
    html_part = MIMEText(html_body, "html", "utf-8")
    msg_body.attach(html_part)
    msg.attach(msg_body)

    # 2. PDF Attachment
    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(pdf_attachment)

    # 3. Dispatch via SES send_raw_email
    return ses_client.send_raw_email(
        Source=sender,
        Destinations=[receiver],
        RawMessage={"Data": msg.as_bytes()}
    )


def _safe_int(value, name):
    """Validates a partition value is a plain integer string — prevents SQL injection."""
    try:
        return str(int(value))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid partition value for '{name}': {value!r}")


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    target_year = _safe_int(now.year, "year")
    target_month = _safe_int(now.month, "month")
    target_day = _safe_int(now.day, "day")
    # Zero-pad month and day for Hive partition compatibility
    target_month = target_month.zfill(2)
    target_day = target_day.zfill(2)
    report_date = f"{target_year}-{target_month}-{target_day}"

    logger.info("Starting daily report generation for date: %s", report_date)

    # 1. Query Fleet Summary
    fleet_query = f"""
    SELECT
      COUNT(*) AS total_readings,
      COUNT(DISTINCT device_id) AS active_devices,
      ROUND(AVG(temperature_c), 2) AS avg_temp,
      ROUND(AVG(health_score), 1) AS avg_health
    FROM telemetry
    WHERE year = '{target_year}' AND month = '{target_month}' AND day = '{target_day}';
    """

    try:
        fleet_results = execute_athena_query(athena_client, fleet_query, ATHENA_DATABASE, ATHENA_WORKGROUP)
        fleet_summary = fleet_results[0] if fleet_results else {}
    except Exception as exc:
        logger.warning("Fleet summary query failed | error=%s", str(exc))
        fleet_summary = {"total_readings": "0", "active_devices": "0", "avg_temp": "0.0", "avg_health": "100"}

    # 2. Query Incidents
    incidents_query = f"""
    SELECT
      evaluated_at,
      device_id,
      severity,
      health_score,
      temperature_c,
      vibration_hz,
      plant_location
    FROM incidents
    WHERE year = '{target_year}' AND month = '{target_month}' AND day = '{target_day}'
    ORDER BY health_score ASC;
    """

    try:
        incidents = execute_athena_query(athena_client, incidents_query, ATHENA_DATABASE, ATHENA_WORKGROUP)
    except Exception as exc:
        logger.warning("Incidents query failed | error=%s", str(exc))
        incidents = []

    # 3. Render HTML Dashboard & Compile PDF Document
    html_content = render_executive_report_html(report_date, fleet_summary, incidents)
    pdf_bytes = generate_pdf_report(report_date, fleet_summary, incidents)
    pdf_filename = f"Daily-IoT-Fleet-Report-{report_date}.pdf"
    s3_report_key = None

    # 4. Save PDF Document to Amazon S3 Data Lake under reports/
    if DATA_LAKE_BUCKET:
        s3_report_key = f"reports/year={target_year}/month={target_month}/{pdf_filename}"
        logger.info(
            "Attempting to archive PDF report to S3 | bucket=%s | key=%s | size_bytes=%d",
            DATA_LAKE_BUCKET, s3_report_key, len(pdf_bytes)
        )
        try:
            s3_client.put_object(
                Bucket=DATA_LAKE_BUCKET,
                Key=s3_report_key,
                Body=pdf_bytes,
                ContentType="application/pdf",
                Metadata={
                    "report-date": report_date,
                    "readings-analyzed": str(fleet_summary.get("total_readings", "0")),
                    "incidents-reported": str(len(incidents)),
                    "generated-by": "iot-daily-reporter"
                }
            )
            logger.info("Successfully archived PDF report to S3 | bucket=%s | key=%s", DATA_LAKE_BUCKET, s3_report_key)
        except Exception as exc:
            logger.error("Failed saving PDF report to S3 | bucket=%s | error=%s", DATA_LAKE_BUCKET, str(exc))
            raise
    else:
        logger.warning("DATA_LAKE_BUCKET environment variable is empty! Skipping S3 PDF archive.")

    # 5. Dispatch Email with PDF Attachment via Amazon SES
    if SENDER_EMAIL and RECEIVER_EMAIL:
        try:
            send_email_with_pdf_attachment(
                sender=SENDER_EMAIL,
                receiver=RECEIVER_EMAIL,
                subject=f"Daily IoT Fleet Report | {report_date}",
                html_body=html_content,
                pdf_bytes=pdf_bytes,
                filename=pdf_filename
            )
            logger.info("Dispatched daily summary email with PDF attachment to %s", RECEIVER_EMAIL)
        except Exception as exc:
            logger.error("Failed sending email via SES | error=%s", str(exc))
            raise

    return {
        "statusCode": 200,
        "report_date": report_date,
        "readings_analyzed": fleet_summary.get("total_readings", "0"),
        "incidents_reported": len(incidents),
        "pdf_attachment": pdf_filename,
        "s3_report_key": s3_report_key
    }