-- One row per day: the latest landed version of each date.
-- The raw table keeps every version (yearly files plus daily incremental files that refetch
-- the last two weeks, because recent days get revised); latest _ingested_at wins.

WITH source AS (

    SELECT * FROM {{ source('raw_weather', 'raw_weather_daily') }}

),

ranked AS (

    SELECT
        *,
        row_number() OVER (PARTITION BY local_date ORDER BY _ingested_at DESC) AS version_rank
    FROM source

)

SELECT
    local_date,
    mean_temperature,
    min_temperature,
    max_temperature,
    total_precipitation,
    total_rain,
    total_snow,
    snow_on_ground,
    -- ECCC reports the gust direction in tens of degrees (0 to 36), so multiply by 10
    direction_max_gust * 10 AS max_gust_direction_deg,
    speed_max_gust,
    cooling_degree_days,
    heating_degree_days,
    min_rel_humidity,

    -- false for days where the station reported nothing at all (all-null rows)
    COALESCE(
        mean_temperature, min_temperature, max_temperature, total_precipitation, total_rain,
        total_snow, snow_on_ground, direction_max_gust, speed_max_gust, cooling_degree_days,
        heating_degree_days, min_rel_humidity
    ) IS NOT NULL AS has_observations,

    _ingested_at
FROM ranked
WHERE version_rank = 1
