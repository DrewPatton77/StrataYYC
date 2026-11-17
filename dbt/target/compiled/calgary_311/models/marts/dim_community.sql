-- One row per community code. Requests with no community share the "UNKNOWN" row.
-- The source gives community centrepoints, not addresses, and the points within one community
-- differ by a few metres, so each community gets the median point. Numeric area codes such as
-- 01H are areas, not places, so they have no coordinates.
SELECT
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(comm_code as varchar), '')))))           AS community_key,
    COALESCE(comm_code, 'UNKNOWN')               AS community_code,
    COALESCE(MAX(comm_name), 'Unknown')          AS community_name,
    COALESCE(bool_or(is_unnamed_area), false)    AS is_unnamed_area,
    CASE WHEN COALESCE(bool_or(is_unnamed_area), false) THEN NULL
         ELSE approx_percentile(longitude, 0.5) END AS centre_longitude,
    case when COALESCE(bool_or(is_unnamed_area), false) THEN NULL
         ELSE approx_percentile(latitude, 0.5) END AS centre_latitude
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
GROUP BY comm_code