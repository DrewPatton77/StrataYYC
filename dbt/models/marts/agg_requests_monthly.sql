-- Dashboard table: one row per month, service group, channel group and legacy flag.
-- Months are request months: requests_closed and median_days_to_close describe the requests
-- opened in that month, so recent months read low until their requests close.
-- Duplicates are counted separately, and bulk closures are left out of the median.
-- For trends use reporting_group_name: it stays the same when the City renames a group.
SELECT
    DATE_TRUNC('month', d.date_day)                          AS month_start,
    d.year_month,
    s.service_group,
    s.reporting_group,
    s.reporting_group_name,
    ch.channel_group,
    f.is_legacy_service,
    COUNT_IF(NOT f.is_duplicate)                             AS requests,
    COUNT_IF(f.is_duplicate)                                 AS duplicate_requests,
    COUNT_IF(f.is_closed AND NOT f.is_duplicate)             AS requests_closed,
    COUNT_IF(f.is_bulk_closure AND NOT f.is_duplicate)       AS bulk_closure_requests,
    APPROX_PERCENTILE(
        CASE WHEN NOT f.is_duplicate AND NOT f.is_bulk_closure THEN f.days_to_close END, 0.5
    )                                                        AS median_days_to_close
FROM {{ ref('fct_service_requests') }} f
JOIN {{ ref('dim_date') }} d       ON d.date_key = f.requested_date_key
JOIN {{ ref('dim_service') }} s    ON s.service_key = f.service_key
JOIN {{ ref('dim_channel') }} ch   ON ch.channel_key = f.channel_key
GROUP BY 1, 2, 3, 4, 5, 6, 7