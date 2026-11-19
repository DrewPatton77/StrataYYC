"""Export dbt marts from Athena to CSV files for the Tableau dashboard.

Each table is queried with Athena and the result CSV (which has a header row) is saved to a stable
file name, both locally and under s3://<bucket>/exports/. A table that returns no rows is an error,
so a bad run never overwrites the last good file.
"""

import os
import time
from pathlib import Path

import boto3

DATABASE = "calgary_311_dbt_marts"
WORKGROUP = "calgary-311"
S3_PREFIX = "exports"
REGION = "ca-west-1"

# The tables the dashboard reads. Add a name here to export another mart.
EXPORT_TABLES = [
    "agg_requests_monthly",
    "agg_requests_community_yearly",
    "fct_daily_requests",
]


def dbt_session() -> boto3.Session:
    """A session with the dbt IAM user's keys, which can run Athena queries and write to the bucket.
    The pipeline user's keys (the container's default) cannot query Athena."""
    return boto3.Session(
        aws_access_key_id=os.environ["DBT_AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["DBT_AWS_SECRET_ACCESS_KEY"],
        region_name=REGION,
    )


def _run_query(
    athena, sql: str, workgroup: str, timeout: float = 900, poll: float = 2
) -> str:
    """Run a query and return the S3 location of its CSV result."""
    query_id = athena.start_query_execution(QueryString=sql, WorkGroup=workgroup)[
        "QueryExecutionId"
    ]
    deadline = time.monotonic() + timeout
    while True:
        execution = athena.get_query_execution(QueryExecutionId=query_id)[
            "QueryExecution"
        ]
        state = execution["Status"]["State"]
        if state == "SUCCEEDED":
            return execution["ResultConfiguration"]["OutputLocation"]
        if state in ("FAILED", "CANCELLED"):
            reason = execution["Status"].get("StateChangeReason", "no reason given")
            raise RuntimeError(f"Athena query {state.lower()}: {reason}")
        if time.monotonic() > deadline:
            athena.stop_query_execution(QueryExecutionId=query_id)
            raise TimeoutError(
                f"Athena query {query_id} did not finish in {timeout:.0f} seconds"
            )
        time.sleep(poll)


def _split_s3_uri(uri: str) -> tuple[str, str]:
    bucket, _, key = uri.removeprefix("s3://").partition("/")
    return bucket, key


def export_tables(
    tables: list[str],
    out_dir: str | Path,
    bucket: str,
    *,
    database: str = DATABASE,
    workgroup: str = WORKGROUP,
    session: boto3.Session | None = None,
    poll: float = 2,
) -> dict[str, int]:
    """Export each table to <out_dir>/<table>.csv and s3://<bucket>/exports/<table>.csv.
    Returns the number of data rows written per table."""
    session = session or dbt_session()
    athena, s3 = session.client("athena"), session.client("s3")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_written = {}
    for table in tables:
        result_uri = _run_query(
            athena, f'select * from "{database}"."{table}"', workgroup, poll=poll
        )
        result_bucket, result_key = _split_s3_uri(result_uri)

        # Download to a temporary name first, so a half-written or empty file never replaces a good one.
        tmp_path = out_dir / f"{table}.csv.tmp"
        s3.download_file(result_bucket, result_key, str(tmp_path))
        with open(tmp_path, encoding="utf-8") as f:
            rows = sum(1 for _ in f) - 1  # minus the header row
        if rows < 1:
            tmp_path.unlink()
            raise RuntimeError(f"{table} returned no rows; keeping the previous export")
        os.replace(tmp_path, out_dir / f"{table}.csv")

        # Server-side copy to a stable key, so the S3 copy never needs the file contents again.
        s3.copy_object(
            Bucket=bucket,
            Key=f"{S3_PREFIX}/{table}.csv",
            CopySource={"Bucket": result_bucket, "Key": result_key},
        )
        rows_written[table] = rows
    return rows_written
