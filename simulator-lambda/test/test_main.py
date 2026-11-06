import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Ensure src/ is discoverable on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

class TestSimulatorLambda(unittest.TestCase):

    @patch('lambda_function.table')
    def test_default_telemetry_batch(self, mock_table):
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch

        import lambda_function
        event = {"body": json.dumps({"count": 5})}
        response = lambda_function.lambda_handler(event, None)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['records_written'], 5)
        self.assertEqual(body['anomalies_created'], 0)
        self.assertEqual(body['errors_injected'], 0)
        self.assertEqual(mock_batch.put_item.call_count, 5)

    @patch('lambda_function.table')
    def test_force_anomaly_injection(self, mock_table):
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch

        import lambda_function
        event = {"body": json.dumps({"count": 3, "force_anomaly": True})}
        response = lambda_function.lambda_handler(event, None)

        body = json.loads(response['body'])
        self.assertEqual(body['records_written'], 3)
        self.assertEqual(body['anomalies_created'], 1)

    @patch('lambda_function.table')
    def test_force_error_injection(self, mock_table):
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch

        import lambda_function
        event = {"body": json.dumps({"count": 3, "force_error": True})}
        response = lambda_function.lambda_handler(event, None)

        body = json.loads(response['body'])
        self.assertEqual(body['records_written'], 3)
        self.assertEqual(body['errors_injected'], 1)

if __name__ == '__main__':
    unittest.main()