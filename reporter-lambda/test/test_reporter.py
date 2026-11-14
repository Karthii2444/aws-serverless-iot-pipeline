import sys
import os
import unittest

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['DATA_LAKE_BUCKET'] = 'test-iot-telemetry-lake'
os.environ['SENDER_EMAIL'] = 'sender@example.com'
os.environ['RECEIVER_EMAIL'] = 'operator@example.com'

from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import main


class TestReporterLambda(unittest.TestCase):

    def setUp(self):
        main.DATA_LAKE_BUCKET = 'test-iot-telemetry-lake'
        main.SENDER_EMAIL = 'sender@example.com'
        main.RECEIVER_EMAIL = 'operator@example.com'

    @patch('main.glue_client')
    @patch('main.s3_client')
    @patch('main.ses_client')
    @patch('main.execute_athena_query')
    def test_successful_daily_report_with_pdf_attachment_and_s3_save(self, mock_query, mock_ses, mock_s3, mock_glue):
        mock_glue.get_table.return_value = {"Table": {"Name": "mock"}}
        mock_query.side_effect = [
            [{"total_readings": "100", "active_devices": "5", "avg_temp": "68.4", "avg_health": "92.0"}],
            [{
                "evaluated_at": "2026-11-06T12:00:00Z",
                "device_id": "sensor-press-003",
                "severity": "CRITICAL",
                "health_score": "25",
                "temperature_c": "98.7",
                "vibration_hz": "142.5",
                "plant_location": "Bengaluru-Plant-01"
            }]
        ]

        result = main.lambda_handler({}, None)
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(result['readings_analyzed'], "100")
        self.assertEqual(result['incidents_reported'], 1)
        self.assertIn(".pdf", result['pdf_attachment'])
        self.assertIn("reports/year=", result['s3_report_key'])

        # Verify S3 put_object was called to archive the PDF
        mock_s3.put_object.assert_called_once()
        s3_call = mock_s3.put_object.call_args[1]
        self.assertEqual(s3_call['Bucket'], 'test-iot-telemetry-lake')
        self.assertEqual(s3_call['ContentType'], 'application/pdf')

        # Verify SES send_raw_email was called with MIME data
        mock_ses.send_raw_email.assert_called_once()

    @patch('main.glue_client')
    @patch('main.s3_client')
    @patch('main.ses_client')
    @patch('main.execute_athena_query')
    def test_daily_report_zero_incidents(self, mock_query, mock_ses, mock_s3, mock_glue):
        mock_glue.get_table.return_value = {"Table": {"Name": "mock"}}
        mock_query.side_effect = [
            [{"total_readings": "50", "active_devices": "5", "avg_temp": "62.0", "avg_health": "100.0"}],
            []
        ]

        result = main.lambda_handler({}, None)
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(result['incidents_reported'], 0)
        mock_s3.put_object.assert_called_once()
        mock_ses.send_raw_email.assert_called_once()

    @patch('main.glue_client')
    def test_missing_table_raises_runtime_error(self, mock_glue):
        """Verifies Lambda fails fast and raises RuntimeError when Athena/Glue table is missing."""
        mock_glue.get_table.side_effect = Exception("EntityNotFoundException: Table not found")

        with self.assertRaises(RuntimeError) as ctx:
            main.lambda_handler({}, None)

        self.assertIn("does not exist in database", str(ctx.exception))

    @patch('main.glue_client')
    @patch('main.execute_athena_query')
    def test_athena_query_failure_raises_error(self, mock_query, mock_glue):
        """Verifies Lambda fails and raises RuntimeError when Athena SQL execution fails."""
        mock_glue.get_table.return_value = {"Table": {"Name": "mock"}}
        mock_query.side_effect = RuntimeError("Athena query failed with FAILED: SYNTAX_ERROR")

        with self.assertRaises(RuntimeError) as ctx:
            main.lambda_handler({}, None)

        self.assertIn("Fleet summary query failed", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()