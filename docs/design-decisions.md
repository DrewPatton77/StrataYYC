# Design decisions

- **Append-only raw layer.** Raw files are never edited. A request that changes appears again in a later file, and
  the intermediate model keeps the latest version by `updated_date`, then `_ingested_at`. Loads are safe to re-run.
- **Incremental loads with an overlap.** The 311 dates have no time of day, and requests are updated after the fact,
  so each daily load re-reads the last three days before the newest `updated_date`. Where `updated_date` is null it
  falls back to `closed_date`, then `requested_date`. Weather refetches the last 14 days because recent days are revised.
- **Counts are checked on every load.** Each fetch compares rows fetched against the API's expected count and records
  the result in `_manifest.csv`. In Airflow a mismatch fails the task so it retries.
- **Shared extractor base class.** `BaseExtractor` holds the retrying HTTP calls, manifest writing and S3 upload.
  Each source's class only holds its own pagination and schema.
- **Cleaning is in the pipeline, not in a notebook.** Everything that changes the data, including the service-name
  map, is dbt SQL under version control and covered by tests. The notebook documents why each rule exists.
- **dbt runs in its own virtual environment** inside the Airflow image, so its packages cannot clash with Airflow's.
- **Two IAM users with least privilege.** The pipeline user can only read and write the bucket. The dbt user can run
  Athena queries and build tables. Policies are in `infra/iam/`.
- **Status is the source of truth for open and closed.** The data has inconsistencies (below), so staging flags
  conflicting rows instead of correcting them.

Back to the [README](../README.md).