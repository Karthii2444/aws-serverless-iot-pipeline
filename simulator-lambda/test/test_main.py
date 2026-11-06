import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Ensure src/ is discoverable on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

class TestSimulatorLambda(unittest.TestCase):

    @patch('main.table')
    def test_default_telemetry_batch(self, mock_table):
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch

        import main
        event = {"body": json.dumps({"count": 5})}
        response = main.lambda_handler(event, None)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['records_written'], 5)
        self.assertEqual(body['anomalies_created'], 0)
        self.assertEqual(body['errors_injected'], 0)
        self.assertEqual(mock_batch.put_item.call_count, 5)

    @patch('main.table')
    def test_random_anomaly_injection(self, mock_table):
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch

        import main
        event = {"body": json.dumps({"count": 20, "force_anomaly": True})}
        response = main.lambda_handler(event, None)

        body = json.loads(response['body'])
        self.assertEqual(body['records_written'], 20)
        # Verifies 2 to 3 anomalies are injected for a batch of 20
        self.assertGreaterEqual(body['anomalies_created'], 2)
        self.assertLessEqual(body['anomalies_created'], 3)
        self.assertEqual(body['errors_injected'], 0)

    @patch('main.table')
    def test_random_error_injection(self, mock_table):
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch

        import main
        event = {"body": json.dumps({"count": 20, "force_error": True})}
        response = main.lambda_handler(event, None)

        body = json.loads(response['body'])
        self.assertEqual(body['records_written'], 20)
        # Verifies 2 to 3 schema errors are injected for a batch of 20
        self.assertGreaterEqual(body['errors_injected'], 2)
        self.assertLessEqual(body['errors_injected'], 3)
        self.assertEqual(body['anomalies_created'], 0)

if __name__ == '__main__':
    unittest.main()