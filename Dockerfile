ARG AIRFLOW_VERSION=3.4.0
FROM apache/airflow:${AIRFLOW_VERSION}

# need to install polars and boto3
RUN pip install --no-cache-dir polars boto3

# A folder for the SQLite metadata database.
RUN mkdir -p /opt/airflow/state