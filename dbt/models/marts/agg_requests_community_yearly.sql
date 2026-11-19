-- Dashboard table for maps: one row per year, community and service group.
-- Requests with no community code share the Unknown row (has_community = false), and numbered
-- areas such as 01A are kept with null coordinates. Use is_mappable to filter maps.
-- Duplicates are excluded. For trends use reporting_group_name: it stays the same when the City
-- renames a group.
SELECT
    d.year_num,
    c.community_code,
    c.community_name,
    c.has_community,
    c.is_unnamed_area,
    c.is_mappable,
    c.centre_longitude,
    c.centre_latitude,
    s.service_group,
    s.reporting_group,
    s.reporting_group_name,
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
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11