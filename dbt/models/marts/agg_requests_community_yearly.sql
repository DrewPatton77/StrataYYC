-- Dashboard table for maps: one row per year, community and service group.
-- Unnamed areas (codes such as 01A) are kept, with null coordinates. Duplicates are excluded.
SELECT
    d.year_num,
    c.community_code,
    c.community_name,
    c.is_unnamed_area,
    c.centre_longitude,
    c.centre_latitude,
    s.service_group,
    COUNT(*)                                                 AS requests,
    COUNT_IF(f.is_closed)                                    AS requests_closed,
    APPROX_PERCENTILE(
        CASE WHEN NOT f.is_bulk_closure THEN f.days_to_close END, 0.5
    )                                                        AS median_days_to_close
FROM {{ ref('fct_service_requests') }} f
JOIN {{ ref('dim_date') }} d       ON d.date_key = f.requested_date_key
JOIN {{ ref('dim_service') }} s    ON s.service_key = f.service_key
JOIN {{ ref('dim_community') }} c  ON c.community_key = f.community_key
WHERE NOT f.is_duplicate
GROUP BY 1, 2, 3, 4, 5, 6, 7