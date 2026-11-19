# Setup guide

Prerequisites: Docker, Python 3.12 or later with [uv](https://docs.astral.sh/uv/), an AWS account, the `ca-west-1`
(Calgary) region.

1. **AWS setup.** Create an S3 bucket, a $5 AWS Budgets alert, and an Athena workgroup named `calgary-311` with its results
   in `s3://<bucket>/athena-results/` and a per-query scan limit. Create two IAM users and attach the policies in
   `infra/iam/` (replace `ACCOUNT_ID` in the dbt policy). Create an access key for each.
2. **Configure.** `cp .env.example .env` and fill in the bucket and both sets of keys. Then
   `cp dbt/profiles.yml.example dbt/.dbt/profiles.yml` and adjust the bucket name.
3. **Backfill.** From the repository root, after `uv sync`:
   ```
   PYTHONPATH=include uv run python -c "from extract_311 import ServiceRequestExtractor as E; E().run(); E().upload_to_s3()"
   PYTHONPATH=include uv run python -c "from extract_weather import CalgaryWeatherExtractor as E; E().run(); E().upload_to_s3()"
   ```
   The 311 backfill takes about 15 minutes. Files go to `raw/` and to S3.
4. **Create the Athena tables.** Run the `CREATE EXTERNAL TABLE` statements in `sql/` in the Athena console.
5. **Start Airflow.** `docker compose up -d --build`. Open http://localhost:8080 (the admin password is in
   `docker compose logs airflow`), unpause `daily` and trigger it once.
6. **Check.** The `dbt_build` task log should end with no errors. Two warnings are expected, for the known data
   issues above (one ID with a mismatched year, and requests with a location but no coordinates).

To run dbt by hand: `uv sync`, export the dbt user's keys, then from `dbt/` run `dbt build --profiles-dir .dbt`.

## Testing and CI

- `pytest` runs a handful of unit tests on the logic that is easiest to get wrong: the incremental filter, month
  boundaries, retry and give-up behaviour, manifest writing and pagination.
- `dbt build` runs more than 50 data tests: uniqueness, not-null, accepted values, relationships between the fact and
  every dimension, row-count reconciliation between staging, the fact table and the daily table, and checks that retired
  names and spelling variants do not leak into the marts.
- GitHub Actions runs `ruff`, `pytest` and `dbt parse` on every push and pull request. CI has no AWS credentials, so
  the dbt tests themselves run in Airflow against the real data.

## Cost

S3 and Athena only. At this data size (under a few GB of Parquet) the estimated cost is about $1 a month or less. Airflow
runs locally. An AWS Budgets alert and an Athena per-query scan limit guard against surprises.

## Repository structure

```
.
├── README.md
├── docker-compose.yml          local Airflow (standalone) with SQLite
├── Dockerfile                  Airflow image plus polars, boto3 and a separate dbt virtual environment
├── .env.example                settings and AWS keys (copy to .env; never commit .env)
├── pyproject.toml              dependencies (uv), ruff and pytest settings
├── data_exploration.ipynb      profiling and cleaning decisions behind the dbt rules
├── dags/
│   └── daily.py                the DAG: extract and upload in parallel, then dbt build
├── include/
│   ├── base_extractor.py       BaseExtractor: retrying requests, manifest, S3 upload
│   ├── extract_311.py          ServiceRequestExtractor: monthly backfill, incremental load
│   └── extract_weather.py      CalgaryWeatherExtractor: yearly backfill, incremental load
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example    copy to dbt/.dbt/profiles.yml (never commit credentials)
│   ├── requirements.txt        pinned dbt-core and dbt-athena
│   ├── ci/profiles.yml         placeholder profile so CI can parse the project
│   ├── macros/                 date and surrogate key helpers, clean_text
│   ├── models/
│   │   ├── intermediate/       base_service_requests
│   │   ├── staging/            sources, service_name_map, stg_service_requests, stg_weather_daily
│   │   └── marts/              dim_*, fct_service_requests, fct_daily_requests
│   └── tests/                  singular data tests
├── sql/
│   ├── 01_athena_raw_311.sql   Athena table over the raw 311 files, plus checks
│   └── 02_athena_raw_weather.sql
├── scripts/
│   └── check_weather.py        checks on the raw weather files
├── infra/iam/
│   ├── pipeline_policy.json    S3 access for the pipeline user
│   └── dbt_policy.json         Athena, Glue and S3 access for the dbt user (fill in ACCOUNT_ID)
├── tests/                      a handful of focused unit tests (no network, no AWS)
└── .github/workflows/ci.yml
```

Back to the [README](../README.md).