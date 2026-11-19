-- One row per community code. Requests with no community code share the "Unknown" row.
-- The source gives community centrepoints, not addresses, and the points within one community
-- differ by a few metres, so each community gets the median point. Numeric area codes such as
-- 01H are areas, not places, so they have no coordinates.
-- has_community is false for the Unknown row; is_mappable is true only for named communities
-- that have a point, and is what dashboards use to filter maps.
SELECT
    {{ surrogate_key(['comm_code']) }}                                               AS community_key,
    COALESCE(comm_code, 'UNKNOWN')                                                   AS community_code,
    CASE WHEN comm_code IS NULL THEN 'Unknown'
         ELSE COALESCE(MAX(comm_name), 'Unknown') END                                AS community_name,
    comm_code IS NOT NULL                                                            AS has_community,
    CASE WHEN comm_code IS NULL THEN false
         ELSE COALESCE(bool_or(is_unnamed_area), false) END                          AS is_unnamed_area,
    comm_code IS NOT NULL AND NOT COALESCE(bool_or(is_unnamed_area), false)          AS is_mappable,
    CASE WHEN comm_code IS NULL OR COALESCE(bool_or(is_unnamed_area), false) THEN NULL
         ELSE APPROX_PERCENTILE(longitude, 0.5) END                                  AS centre_longitude,
    CASE WHEN comm_code IS NULL OR COALESCE(bool_or(is_unnamed_area), false) THEN NULL
         ELSE APPROX_PERCENTILE(latitude, 0.5) END                                   AS centre_latitude
FROM {{ ref('stg_service_requests') }}
GROUP BY comm_code