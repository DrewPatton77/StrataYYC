-- Athena table over the raw weather files.

CREATE EXTERNAL TABLE IF NOT EXISTS calgary_311.raw_weather_daily(
    local_date          date,
    mean_temperature    double,
    min_temperature     double,
    max_temperature     double,
    total_precipitation double,
    total_rain          double,
    total_snow          double,
    snow_on_ground      double,
    direction_max_gust  double,
    speed_max_gust      double,
    cooling_degree_days double,
    heating_degree_days double,
    min_rel_humidity    double,
    `_ingested_at`      string
)
STORED AS PARQUET
LOCATION 's3://calgary-services-and-requests-data-pipeline/raw/weather/';

-- check: rows, distinct dates, first and last date.
-- 2012-07-12 to 2026-11-10; distinct dates should match.
-- incremental files exists.
SELECT count(*) AS total_rows,
       count(DISTINCT local_date) AS distinct_dates,
       min(local_date) AS first_date,
       max(local_date) AS last_date
FROM calgary_311.raw_weather_daily;