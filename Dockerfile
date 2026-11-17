ARG AIRFLOW_VERSION=3.4.0
FROM apache/airflow:${AIRFLOW_VERSION}

# A C compiler, because one of dbt-athena's dependencies (mmh3) has no prebuilt wheel for this
# image and is compiled during install.
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*
USER airflow
# need to install polars and boto3
RUN pip install --no-cache-dir polars boto3

COPY dbt/requirements.txt /tmp/dbt-requirements.txt
RUN python -m venv /home/airflow/dbt-venv \
 && /home/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt

# A folder for the SQLite metadata database.
RUN mkdir -p /opt/airflow/state