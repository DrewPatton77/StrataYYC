"""
Daily Calgary 311 pipeline: extract and upload every source, run dbt, then export the dashboard tables.

    extract_<source> -> upload_<source> --\
    extract_<source> -> upload_<source> ---> dbt_build -> export_marts

There is one extract -> upload chain per source in pipeline.yml, so adding a source needs no change
here thus making is modular. The chains run in parallel. dbt starts only when every upload has succeeded, and the export
only when dbt (including its tests) has passed. The steps are the same functions the CLI runs
(`uv run stratayyc run`), so the DAG and the command line cannot drift apart.
"""

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import dag, task

# Airflow puts dags/ on the import path but not src/ (mounted by docker-compose.yml).
sys.path.insert(0, "/opt/airflow/src")
from stratayyc import steps
from stratayyc.config import load_config

CFG = load_config(
    "/opt/airflow/pipeline.yml"
)  # raw/, dbt/ and exports/ resolve next to this file


def _source_chain(name: str):
    source = CFG.sources[name]

    # strict extract: a count mismatch fails the task, so Airflow retries it.
    @task(task_id=f"extract_{name}")
    def extract() -> None:
        steps.extract(source, CFG.base_dir)

    # Bucket name and AWS keys come from the container's environment (see .env).
    @task(task_id=f"upload_{name}")
    def upload() -> int:
        return steps.upload(source, CFG.base_dir)

    return extract() >> upload()


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
    # One retry only: a failing dbt test fails again, so retrying every ten minutes would just
    # repeat the same Athena queries. A failed test fails the task; warnings do not.
    @task(retries=1, execution_timeout=timedelta(hours=1))
    def dbt_build() -> None:
        steps.run_dbt(CFG)

    # Uses the dbt user's keys: the pipeline user cannot query Athena.
    @task
    def export_marts() -> dict:
        return steps.export(CFG)

    # dbt waits for every upload, so the marts never mix new requests with stale weather.
    # The export waits for dbt, so a failed test never publishes new files.
    [_source_chain(name) for name in CFG.sources] >> dbt_build() >> export_marts()


daily()
