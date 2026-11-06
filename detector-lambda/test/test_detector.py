import sys
import os
import json
import unittest

# Set dummy AWS credentials, region & env vars so Boto3 initializes offline
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:iot-critical-alerts'
os.environ['SQS_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/iot-telemetry-queue'
os.environ['PLANT_METADATA_JSON'] = json.dumps({
    "sensor-press-001": {"plant": "Bengaluru-Plant-01", "team": "Mechanical-Alpha"},
    "sensor-press-002": {"plant": "Bengaluru-Plant-01", "team": "Mechanical-Alpha"},
    "sensor-press-003": {"plant": "Bengaluru-Plant-01", "team": "Hydraulics-Beta"},
    "sensor-press-004": {"plant": "Chennai-Plant-02", "team": "Hydraulics-Beta"},
    "sensor-press-005": {"plant": "Chennai-Plant-02", "team": "Electrical-Gamma"}
})

from unittest.mock import patch

# Ensure detector-lambda/src is discoverable on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import main


class TestDetectorLambda(unittest.TestCase):

    def setUp(self):
        main.SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
        main.SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']

    @patch('main.sqs_client')
    @patch('main.sns_client')
    def test_healthy_record_enrichment_no_sns(self, mock_sns, mock_sqs):
        stream_event = {
            "Records": [{
                "eventName": "INSERT",
                "dynamodb": {
                    "NewImage": {
                        "device_id": {"S": "sensor-press-004"},
                        "timestamp": {"S": "2026-11-06T08:00:00Z"},
                        "telemetry_id": {"S": "uuid-healthy-1"},
                        "temperature_c": {"N": "65.0"},
                        "vibration_hz": {"N": "35.0"},
                        "pressure_psi": {"N": "102.0"},
                        "battery_pct": {"N": "90"}
                    }
                }
            }]
        }

        result = main.lambda_handler(stream_event, None)
        self.assertEqual(result['records_processed'], 1)
        self.assertEqual(result['incidents_dispatched'], 0)
        self.assertEqual(result['sqs_forwarded'], 1)
        mock_sns.publish.assert_not_called()

        # Verify enriched payload sent to SQS uses env var metadata
        sqs_call_args = mock_sqs.send_message.call_args[1]
        payload = json.loads(sqs_call_args['MessageBody'])
        self.assertEqual(payload['health_score'], 100)
        self.assertEqual(payload['severity'], 'NORMAL')
        self.assertFalse(payload['is_incident'])
        self.assertEqual(payload['plant_location'], 'Chennai-Plant-02')
        self.assertEqual(payload['maintenance_team'], 'Hydraulics-Beta')

    @patch('main.sqs_client')
    @patch('main.sns_client')
    def test_critical_anomaly_triggers_sns_and_sqs(self, mock_sns, mock_sqs):
        stream_event = {
            "Records": [{
                "eventName": "INSERT",
                "dynamodb": {
                    "NewImage": {
                        "device_id": {"S": "sensor-press-003"},
                        "timestamp": {"S": "2026-11-06T08:05:00Z"},
                        "telemetry_id": {"S": "uuid-anomaly-1"},
                        "temperature_c": {"N": "98.5"},
                        "vibration_hz": {"N": "145.0"},
                        "pressure_psi": {"N": "120.0"},
                        "battery_pct": {"N": "75"}
                    }
                }
            }]
        }

        result = main.lambda_handler(stream_event, None)
        self.assertEqual(result['records_processed'], 1)
        self.assertEqual(result['incidents_dispatched'], 1)
        self.assertEqual(result['sqs_forwarded'], 1)
        mock_sns.publish.assert_called_once()

        # Verify SNS ticket content
        sns_args = mock_sns.publish.call_args[1]
        self.assertIn("CRITICAL ALERT", sns_args['Subject'])
        self.assertIn("CRITICAL_OVERHEAT", sns_args['Message'])
        self.assertIn("Bengaluru-Plant-01", sns_args['Message'])

        # Verify SQS payload is marked as an incident for S3 incidents/ folder
        sqs_payload = json.loads(mock_sqs.send_message.call_args[1]['MessageBody'])
        self.assertEqual(sqs_payload['severity'], 'CRITICAL')
        self.assertTrue(sqs_payload['is_incident'])
        self.assertEqual(sqs_payload['health_score'], 5)

    @patch('main.sqs_client')
    @patch('main.sns_client')
    def test_corrupted_record_passes_to_sqs_for_dlq(self, mock_sns, mock_sqs):
        stream_event = {
            "Records": [{
                "eventName": "INSERT",
                "dynamodb": {
                    "NewImage": {
                        "device_id": {"S": "sensor-press-002"},
                        "timestamp": {"S": "2026-11-06T08:10:00Z"},
                        "telemetry_id": {"S": "uuid-corrupt-1"},
                        "temperature_c": {"S": "CORRUPTED_STRING_VALUE"},
                        "vibration_hz": {"N": "40.0"}
                    }
                }
            }]
        }

        result = main.lambda_handler(stream_event, None)
        self.assertEqual(result['records_processed'], 1)
        self.assertEqual(result['incidents_dispatched'], 0)
        self.assertEqual(result['sqs_forwarded'], 1)
        mock_sns.publish.assert_not_called()

        sqs_payload = json.loads(mock_sqs.send_message.call_args[1]['MessageBody'])
        self.assertEqual(sqs_payload['severity'], 'UNVALIDATED')
        self.assertFalse(sqs_payload['is_incident'])


if __name__ == '__main__':
    unittest.main()