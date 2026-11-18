-- The dashboard tables must add up to the fact table: nothing dropped by a join, nothing counted twice.
WITH fact AS (

    SELECT
        COUNT_IF(NOT is_duplicate) AS requests,
        COUNT_IF(is_duplicate)     AS duplicate_requests
    FROM {{ ref('fct_service_requests') }}

),

monthly AS (

    SELECT SUM(requests) AS requests, SUM(duplicate_requests) AS duplicate_requests
    FROM {{ ref('agg_requests_monthly') }}

),

community AS (

    SELECT SUM(requests) AS requests
    FROM {{ ref('agg_requests_community_yearly') }}

)

SELECT
    fact.requests           AS fact_requests,
    monthly.requests        AS monthly_requests,
    community.requests      AS community_requests,
    fact.duplicate_requests AS fact_duplicates,
    monthly.duplicate_requests AS monthly_duplicates
FROM fact
CROSS JOIN monthly
CROSS JOIN community
WHERE fact.requests <> monthly.requests
   OR fact.duplicate_requests <> monthly.duplicate_requests
   OR fact.requests <> community.requests