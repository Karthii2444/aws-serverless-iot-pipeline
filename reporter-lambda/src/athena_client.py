import time
import logging

logger = logging.getLogger("iot-athena-client")


def execute_athena_query(athena_client, query_string, database, workgroup, max_attempts=30, backoff_sec=1.5):
    """
    Submits an asynchronous SQL query to Athena, polls until finished,
    and returns a list of dictionaries representing the result rows.
    """
    logger.info("Executing Athena query: %s", query_string.strip().replace("\n", " "))

    response = athena_client.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={"Database": database},
        WorkGroup=workgroup
    )
    query_id = response["QueryExecutionId"]

    # Poll query status with backoff
    for attempt in range(max_attempts):
        status = athena_client.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            logger.info("Athena query %s succeeded in %d polls", query_id, attempt + 1)
            break
        elif state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            raise RuntimeError(f"Athena query {query_id} ended with {state}: {reason}")

        time.sleep(backoff_sec)
    else:
        raise TimeoutError(f"Athena query {query_id} timed out after {max_attempts} polling attempts")

    # Fetch and parse results
    results = athena_client.get_query_results(QueryExecutionId=query_id)
    return parse_athena_result_set(results)


def parse_athena_result_set(result_set):
    """Converts Athena ResultSet Rows into a list of key-value dictionaries."""
    rows = result_set.get("ResultSet", {}).get("Rows", [])
    if not rows:
        return []

    # First row is always column headers
    headers = [col.get("VarCharValue", "") for col in rows[0].get("Data", [])]
    parsed_rows = []

    for row in rows[1:]:
        data_values = [col.get("VarCharValue", "") for col in row.get("Data", [])]
        parsed_rows.append(dict(zip(headers, data_values)))

    return parsed_rows