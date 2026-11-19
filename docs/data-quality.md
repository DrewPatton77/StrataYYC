# Data quality findings

Found while profiling the full history. They are encoded as dbt tests with warn or error thresholds.

- About 4,700 requests have status Open but carry a closed date. They are rare before 2021 and rise every year after.
  Six Closed requests from 2014 have no closed date.
- `updated_date` is null for about 0.65% of Closed and 26% of Duplicate (Closed) requests across all versions, so the
  incremental rule needs its fallback.
- Status "TO BE DELETED" appears on 103 requests and is dropped. Service names, agencies, community names and
  location types contain placeholder text and spelling variants, cleaned as described above.
- The channel field changed meaning: Web was folded into Other in March 2021, and Phone faded into Other between
  2022 and 2025, so only the App versus Other split is comparable across all years.
- About 36,850 requests sit in unnamed communities (codes such as `01A`), and 880 requests have a location but no
  coordinates. One request has an ID whose year differs from its requested year. These raise warnings, not errors.
- A few days have unusually many closures from city backlog cleanups, so closure counts are not a clean measure of workload.
- Weather: 91 days have every measure null (mostly 2012 and 2013). `snow_on_ground` is about 61% null,
  `min_rel_humidity` is 100% null for 2012 to 2016, and gust reporting changed over time, so these columns are
  not used for headline analysis. Gust direction is reported in tens of degrees and converted in staging.

Back to the [README](../README.md).