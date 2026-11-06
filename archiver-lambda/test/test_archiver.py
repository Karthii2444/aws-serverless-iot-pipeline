import sys
import os
import json
import unittest

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['DATA_LAKE_BUCKET'] = 'test-iot-telemetry-lake'

from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import main


class TestArchiverLambda(unittest.TestCase):

    def setUp(self):
        main.S3_DATA_LAKE_BUCKET = 'test-iot-telemetry-lake'

    @patch('main.s3_client')
    def test_valid_telemetry_written_to_s3(self, mock_s3):
        sqs_event = {
            "Records": [{
                "messageId": "msg-001",
                "body": json.dumps({
                    "device_id": "sensor-press-001",
                    "timestamp": "2026-11-06T12:00:00Z",
                    "telemetry_id": "uuid-1",
                    "temperature_c": 64.2,
                    "vibration_hz": 32.1,
                    "pressure_psi": 102.0,
                    "battery_pct": 95,
                    "is_incident": False
                })
            }]
        }

        response = main.lambda_handler(sqs_event, None)
        self.assertEqual(len(response['batchItemFailures']), 0)
        self.assertEqual(mock_s3.put_object.call_count, 1)

        call_args = mock_s3.put_object.call_args[1]
        self.assertEqual(call_args['Bucket'], 'test-iot-telemetry-lake')
        self.assertIn("telemetry/year=", call_args['Key'])
        self.assertIn("sensor-press-001", call_args['Body'].decode('utf-8'))
        self.assertEqual(call_args['Metadata']['record-count'], '1')

    @patch('main.s3_client')
    def test_incident_record_written_to_both_telemetry_and_incidents(self, mock_s3):
        sqs_event = {
            "Records": [{
                "messageId": "msg-002",
                "body": json.dumps({
                    "device_id": "sensor-press-003",
                    "timestamp": "2026-11-06T12:00:00Z",
                    "telemetry_id": "uuid-2",
                    "temperature_c": 98.7,
                    "vibration_hz": 142.5,
                    "pressure_psi": 118.0,
                    "battery_pct": 74,
                    "is_incident": True,
                    "severity": "CRITICAL"
                })
            }]
        }

        response = main.lambda_handler(sqs_event, None)
        self.assertEqual(len(response['batchItemFailures']), 0)
        # Must write once to telemetry/ and once to incidents/
        self.assertEqual(mock_s3.put_object.call_count, 2)

        keys = [call[1]['Key'] for call in mock_s3.put_object.call_args_list]
        self.assertTrue(any("telemetry/year=" in k for k in keys))
        self.assertTrue(any("incidents/year=" in k for k in keys))

    @patch('main.s3_client')
    def test_corrupted_message_reported_in_batch_item_failures(self, mock_s3):
        sqs_event = {
            "Records": [
                {
                    "messageId": "msg-good",
                    "body": json.dumps({
                        "device_id": "sensor-press-001",
                        "timestamp": "2026-11-06T12:00:00Z",
                        "telemetry_id": "uuid-good",
                        "temperature_c": 60.0,
                        "vibration_hz": 25.0,
                        "is_incident": False
                    })
                },
                {
                    "messageId": "msg-bad-corrupted",
                    "body": json.dumps({
                        "device_id": "sensor-press-002",
                        "timestamp": "2026-11-06T12:00:00Z",
                        "telemetry_id": "uuid-bad",
                        "temperature_c": "CORRUPTED_STRING_VALUE",
                        "vibration_hz": 40.0
                    })
                }
            ]
        }

        response = main.lambda_handler(sqs_event, None)
        # Good message archived, only bad message reported back to SQS for DLQ retry
        self.assertEqual(len(response['batchItemFailures']), 1)
        self.assertEqual(response['batchItemFailures'][0]['itemIdentifier'], "msg-bad-corrupted")
        self.assertEqual(mock_s3.put_object.call_count, 1)


if __name__ == '__main__':
    unittest.main()