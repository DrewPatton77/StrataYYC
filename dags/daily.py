"""
Run daily tasks: extract 311 and weather data and upload to S3, run dbt.


DAGs:
    extract_incremental -> upload_raw --------\
                                                >-> dbt_build
    extract_weather -> upload_weather --------/
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import dag, task

RAW_DIR = "/opt/airflow/raw/311"
WEATHER_DIR = "/opt/airflow/raw/weather"


def _extractor(module: str, class_name: str, out_dir: str):
    """
    Build an extractor from include/. Airflow puts dags/ on the import path but not include/,
    so add it here. Imported inside the tasks so the scheduler's DAG parsing stays fast.
    """
    import importlib
    import sys

    sys.path.insert(0, "/opt/airflow/include")
    return getattr(importlib.import_module(module), class_name)(out_dir=out_dir)


@dag(
    dag_id="calgary_311_daily",
    schedule="0 12 * * *",  # 12:00 Calgary time; the portal updates arounf 11:02 to 11:13
    start_date=datetime(2026, 11, 1, tzinfo=ZoneInfo("America/Edmonton")),
    catchup=False,  # one run per day from now on. The monthly and yearly extracts did the history
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["calgary-311", "raw", "aws", "dbt"],
)
def daily():
    @task
    def extract_incremental() -> int:
        # Bucket name and AWS keys come from the container's environment (see .env.example).
        extractor = _extractor("extract_311", "ServiceRequestExtractor", RAW_DIR)
        return extractor.upload_to_s3(bucker=os.environ["S3_BUCKET"])

    @task
    def extract_weather() -> int:
        # Refetches the last 14 days: recent days are revised after they are first published.
        return _extractor(
            "extract_weather", "CalgaryWeatherExtractor", WEATHER_DIR
        ).run_incremental(strict=True)

    @task
    def upload_weather(_rows: int) -> int:
        extractor = _extractor(
            "extract_weather", "CalgaryWeatherExtractor", WEATHER_DIR
        )
        return extractor.upload_to_s3(bucker=os.environ["S3_BUCKET"])


daily()
