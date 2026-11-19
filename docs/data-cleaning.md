# Data cleaning

The cleaning rules come from an exploration notebook (`data_exploration.ipynb`) that profiles the full history before
anything is modelled. The rules then live in dbt, so they run on every load and nothing depends on the notebook:

- **Latest version wins.** The raw layer keeps every landed version of a request. `base_service_requests` keeps the
  newest `updated_date`, with `_ingested_at` as the tie-break, and drops the 103 requests whose latest status is
  "TO BE DELETED".
- **Placeholders become null.** Text is trimmed and repeated spaces collapsed. N/A, null, None and blank values become
  null (macro `clean_text`).
- **Retired services are flagged, not dropped.** About 445,000 requests carry a `z` marker (z, ZZZ, Z CT) or words such as
  OLD, DO NOT USE or INTERNAL in the service name. They get `is_legacy_service = true` and the marker is stripped, so
  retired and current names group together.
- **Spelling variants are mapped to one name.** `service_name_map` groups names that match once case and punctuation are
  ignored and picks the most common spelling, with ties broken alphabetically. It is built from the data on every run.
  The result is 1,124 service names, and a dbt test warns if a variant gets through.
- **Backlog cleanups are flagged.** When a service group closes 1,000 or more requests on one day with a median age of
  at least 100 days, those long-open requests get `is_bulk_closure = true`. Five such batches closed 17,798 requests, of which
  16,076 had been open at least 100 days. They are excluded from the median days to close.
- **Channel and areas.** Channel is not comparable across years (see below), so `channel_group` splits App from
  Other channels and `is_channel_detail_reliable` marks the period before March 2021. Unnamed communities such as
  `01A` are flagged with `is_unnamed_area` and get no coordinates in `dim_community`.

Back to the [README](../README.md).