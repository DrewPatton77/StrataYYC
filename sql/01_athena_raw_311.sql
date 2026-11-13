-- Athena setup for the raw 311 layer. Run each statement separately in the Athena query editor,
-- using the workgroup "calgary-311"

-- 1. Database
CREATE DATABASE IF NOT EXISTS calgary_311;

-- 2. Raw table over every Parquet file under raw/311/ (the monthly files and incremental/).
--    Types match SERVIES_REQUEST_SCHEMA in the extract class: three timestamps, two doubles,
--    the rest text. Athena skips files whose names start with an underscore (_manifest.csv is ignored).
CREATE EXTERNAL TABLE IF NOT EXISTS calgary_311.raw_service_requests(
    service_request_id string,
    requested_date     timestamp,
    updated_date       timestamp,
    closed_date        timestamp,
    status_description string,
    source             string,
    service_name       string,
    agency_responsible string,
    comm_code          string,
    comm_name          string,
    location_type      string,
    longitude          double,
    latitude           double,
    `_ingested_at`     string,
)
STORED AS PARQUET
LOCATION 's3://calgary-services-and-requests-data-pipeline/raw/311/';

-- 3. Checks
-- 3a. which files are being read?
SELECT "$path" AS file, count(*) AS n
FROM calgary_311.raw_service_requests
GROUP BY 1
ORDER BY 1;

-- 3b. Rows versus distinct requests. total_rows exceeds distinct_ids by the rows that appear
--     in more than one file (the incremental overlap). distinct_ids should be about 7,550,278
--     plus any requests created since the monthly extract.
SELECT count(*) AS total_rows,
       count(DISTINCT service_request_id) AS distinct_ids
FROM calgary_311.raw_service_requests;

-- 3c. Did the date parsing work?
--     Open requests should have 0 closed dates; every other status should have closed_dates = n.
--     requested_nulls and updated_nulls should be 0 or close to it.
SELECT status_description,
       count(*) AS n,
       count(closed_date) AS closed_dates,
       count_if(requested_date IS NULL) AS requested_nulls,
       count_if(updated_date IS NULL) AS updated_nulls
FROM calgary_311.raw_service_requests
GROUP BY 1
ORDER BY 2 DESC;