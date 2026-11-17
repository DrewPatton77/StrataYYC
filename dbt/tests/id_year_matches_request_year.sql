-- The two-digit year in a request ID should match its request year. One known exception:
-- 13-00221829, requested in 2012. Warn only.
{{ config(severity='warn') }}

SELECT service_request_id, requested_date
FROM {{ ref('stg_service_requests') }}
WHERE TRY_CAST(substr(service_request_id, 1, 2) AS INTEGER) <> YEAR(requested_date) % 100