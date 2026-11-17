-- One row per calendar day, from 2010 (the earliest requests) to a year ahead.
WITH DAYS AS (

    -- cast: Athena can return the sequence as timestamps, which CTAS cannot store here
    SELECT CAST(d AS DATE) AS date_day
    FROM UNNEST(SEQUENCE(DATE '2010-01-01', DATE_ADD('day', 365, CURRENT_DATE), INTERVAL '1' DAY)) AS t(d)

)

SELECT
    (year(date_day) * 10000 + month(date_day) * 100 + day(date_day))                                   AS date_key,
    date_day,
    YEAR(date_day)                                               AS year_num,
    QUARTER(date_day)                                            As quarter_num,
    MONTH(date_day)                                              AS month_num,
    FORMAT_DATETIME(CAST(date_day AS timestamp), 'MMMM')         AS month_name,
    FORMAT_DATETIME(CAST(date_day AS timestamp), 'yyyy-MM')      AS year_month,
    DAY(date_day)                                                AS day_of_month,
    DAY_OF_WEEK(date_day)                                        AS day_of_week_num,   -- 1 = Monday
    FORMAT_DATETIME(CAST(date_day AS timestamp), 'EEEE')         AS day_name,
    DAY_OF_WEEK(date_day) IN (6, 7)                              AS is_weekend
FROM DAYS