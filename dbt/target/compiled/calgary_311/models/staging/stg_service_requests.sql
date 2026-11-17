-- One row per service request: the latest landed version, typed and cleaned.
-- base_service_requests does the dedupe and the first cleaning pass; this model maps service
-- names to their canonical spelling and adds the derived columns. The rules come from the
-- exploration notebook (data_exploration.ipynb); the section numbers refer to it.

WITH mapped AS (

    SELECT
        b.*,
        COALESCE(m.canonical_name, b.service_name_fixed) AS service_name
    FROM "awsdatacatalog"."calgary_311_dbt_intermediate"."base_service_requests" b
    LEFT JOIN "awsdatacatalog"."calgary_311_dbt_staging"."service_name_map" m
        ON m.variant_name = b.service_name_fixed

),

-- S5.4 Service group, communities and channel.
cleaned AS (

    SELECT
        service_request_id,
        requested_date,
        updated_date,
        closed_date,

        status_description,
        source                       AS channel,
        CASE WHEN source = 'App' THEN 'App' ELSE 'Other channels' END AS channel_group,
        -- before March 2021 the Phone, Web and Other split is reliable; afterwards Web and then
        -- Phone are recorded as Other (notebook section 10)
        requested_date < DATE '2021-03-01' AS is_channel_detail_reliable,

        service_name,
        split_part(service_name, ' - ', 1) AS service_group,
        is_legacy_service,
        agency_responsible,

        comm_code,
        REGEXP_REPLACE(comm_name, '\s*/\s*', '/') AS comm_name,
        COALESCE(
            REGEXP_LIKE(REGEXP_REPLACE(comm_name, '\s*/\s*', '/'), '^\d{2}[A-Z]$'),
            false
        ) AS is_unnamed_area,
        location_type,

        longitude,
        latitude,

        status_description IN ('Closed', 'Duplicate (Closed)')           AS is_closed,
        status_description IN ('Duplicate (Closed)', 'Duplicate (Open)') AS is_duplicate,

        ingested_at,

        CASE
            WHEN closed_date IS NOT NULL THEN date_diff('day', requested_date, closed_date)
        END AS days_open

    FROM mapped

),

-- S7. Backlog cleanups: a closed date and service group with many closures of long-open requests.
BATCHES AS (

    SELECT closed_date, service_group
    FROM cleaned
    WHERE closed_date IS NOT NULL
    GROUP BY closed_date, service_group
    HAVING COUNT(*) >= 1000
       AND approx_percentile(days_open, 0.5) >= 100

)

SELECT
    c.service_request_id,
    c.requested_date,
    c.updated_date,
    c.closed_date,

    c.status_description,
    c.channel,
    c.channel_group,
    c.is_channel_detail_reliable,

    c.service_name,
    c.service_group,
    c.is_legacy_service,
    c.agency_responsible,

    c.comm_code,
    c.comm_name,
    c.is_unnamed_area,
    c.location_type,
    c.longitude,
    c.latitude,

    c.is_closed,
    c.is_duplicate,

    -- status is the source of truth; flag rows where the closed date disagrees with it
    (c.is_closed AND c.closed_date IS NULL)
      OR ((NOT c.is_closed) AND c.closed_date IS NOT NULL)              AS has_status_date_conflict,

    CASE
        WHEN c.is_closed AND c.closed_date IS NOT NULL AND c.closed_date >= c.requested_date
            THEN c.days_open
    END                                                                  AS days_to_close,

    -- part of a backlog cleanup, and itself open for at least the threshold
    COALESCE(
        b.closed_date IS NOT NULL AND c.days_open >= 100,
        false
    )                                                                    AS is_bulk_closure,

    c.ingested_at

FROM cleaned c
LEFT JOIN BATCHES b
    ON b.closed_date = c.closed_date
   AND b.service_group = c.service_group