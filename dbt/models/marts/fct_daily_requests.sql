-- One row per day from 2012-01-01 to the latest day that has any requests: 311 volumes joined to that day's weather.
-- Days after that have not been published yet, so they are left out instead of showing zero requests.
-- The latest day can still be incomplete, because requests are added during the day.
-- Data is complete from 2012-01-01. Days before the weather starts (2012-07-12) and days with
-- no mean temperature have has_temperature = false and null weather values; days with no
-- observations at all have has_weather = false.
-- median_days_to_close covers only requests that have closed and leaves out bulk closures,
-- so recent days read low.

WITH daily AS (

    SELECT
        requested_date_key AS date_key,
        count_if(NOT is_duplicate) AS requests,
        count_if(is_duplicate) AS duplicate_requests,
        count_if(is_closed AND NOT is_duplicate) AS requests_closed,
        approx_percentile(
            CASE WHEN NOT is_duplicate AND NOT is_bulk_closure THEN days_to_close END, 0.5
        ) AS median_days_to_close
    FROM {{ ref('fct_service_requests') }}
    GROUP BY 1

)

SELECT
    d.date_key,
    d.date_day,

    COALESCE(daily.requests, 0)           AS requests,
    COALESCE(daily.duplicate_requests, 0) AS duplicate_requests,
    COALESCE(daily.requests_closed, 0)    AS requests_closed,
    daily.median_days_to_close,

    COALESCE(w.has_observations, false)   AS has_weather,
    w.mean_temperature IS NOT NULL        AS has_temperature,
    w.mean_temperature,
    w.min_temperature,
    w.max_temperature,
    w.total_precipitation,
    w.total_rain,
    w.total_snow,
    w.snow_on_ground,
    w.speed_max_gust,
    w.min_rel_humidity
FROM {{ ref('dim_date') }} d
LEFT JOIN daily ON daily.date_key = d.date_key
LEFT JOIN {{ ref('stg_weather_daily') }} w ON w.local_date = d.date_day
WHERE d.date_key BETWEEN 20120101 AND (SELECT MAX(requested_date_key) FROM {{ ref('fct_service_requests') }})