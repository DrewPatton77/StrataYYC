"""
Daily Calgary 311 pipeline: extract 311 changes and recent weather, copy both to S3, run dbt,
then export the dashboard tables to CSV.

    extract_incremental -> upload_raw -------\
                                              >-> dbt_build -> export_marts
    extract_weather -> upload_weather -------/

The two extract chains run in parallel. dbt starts only when both uploads have succeeded, and the
export only when dbt (including its tests) has passed.
"""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import dag, task

RAW_DIR = "/opt/airflow/raw/311"
WEATHER_DIR = "/opt/airflow/raw/weather"
EXPORT_DIR = "/opt/airflow/exports"  # mounted to ./exports on your computer; Tableau reads from there


def _extractor(module: str, class_name: str, out_dir: str):
    """Build an extractor from include/. Airflow puts dags/ on the import path but not include/,
    so add it here. Imported inside the tasks so the scheduler's DAG parsing stays fast."""
    import importlib
    import sys

    sys.path.insert(0, "/opt/airflow/include")
    return getattr(importlib.import_module(module), class_name)(out_dir=out_dir)


@dag(
    dag_id="daily",
    schedule="0 12 * * *",  # 12:00 Calgary time; the portal updates around 11:02 to 11:13
    start_date=datetime(2026, 11, 1, tzinfo=ZoneInfo("America/Edmonton")),
    catchup=False,  # one run per day from now on; the monthly and yearly extracts did the history
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["calgary-311", "raw", "aws", "dbt"],
)
def daily():
    @task
    def extract_incremental() -> int:
        # strict=True: a count mismatch fails the task, so Airflow retries it.
        return _extractor("extract_311", "ServiceRequestExtractor", RAW_DIR).run_incremental(strict=True)

    @task
    def upload_raw(_rows: int) -> int:
        # Bucket name and AWS keys come from the container's environment (see .env).
        extractor = _extractor("extract_311", "ServiceRequestExtractor", RAW_DIR)
        return extractor.upload_to_s3(bucket=os.environ["S3_BUCKET"])

    @task
    def extract_weather() -> int:
        # Refetches the last 14 days: recent days are revised after they are first published.
        return _extractor("extract_weather", "CalgaryWeatherExtractor", WEATHER_DIR).run_incremental(strict=True)

    @task
    def upload_weather(_rows: int) -> int:
        extractor = _extractor("extract_weather", "CalgaryWeatherExtractor", WEATHER_DIR)
        return extractor.upload_to_s3(bucket=os.environ["S3_BUCKET"])

    @task.bash(retries=1, execution_timeout=timedelta(hours=1))
    def dbt_build() -> str:
        # dbt runs from its own virtual environment (see the Dockerfile) so its packages cannot
        # clash with Airflow's. It uses the dbt IAM user's keys, not the pipeline user's: the
        # variables are renamed for this one command only. A failed dbt test fails the task;
        # warnings do not. One retry only: a failing test will fail again, so retrying every
        # ten minutes twice would just repeat the same Athena queries.
        return (
            "set -euo pipefail; "
            "cd /opt/airflow/dbt && "
            'AWS_ACCESS_KEY_ID="$DBT_AWS_ACCESS_KEY_ID" '
            'AWS_SECRET_ACCESS_KEY="$DBT_AWS_SECRET_ACCESS_KEY" '
            "/home/airflow/dbt-venv/bin/dbt build --profiles-dir .dbt"
        )

    @task
    def export_marts() -> dict:
        # Writes each dashboard table to a CSV file, locally and in s3://<bucket>/exports/.
        # Uses the dbt user's keys (read from the container's environment), because the pipeline
        # user cannot query Athena.
        import sys

        sys.path.insert(0, "/opt/airflow/include")
        from export_marts import EXPORT_TABLES, export_tables

        return export_tables(EXPORT_TABLES, EXPORT_DIR, bucket=os.environ["S3_BUCKET"])

    # dbt waits for both uploads, so the marts never mix new requests with stale weather.
    # The export waits for dbt, so a failed test never publishes new files.
    [upload_raw(extract_incremental()), upload_weather(extract_weather())] >> dbt_build() >> export_marts()


daily()