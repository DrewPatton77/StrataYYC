{{ config(materialized='table') }}

WITH source AS (

    SELECT * FROM {{ source('raw_311', 'raw_service_requests') }}

),

-- S4.0 The raw table keeps every stored version of a request (monthly files plus the daily
-- incremental files). The newest updated_date wins; _ingested_at breaks ties and decides
-- when updated_date is null.
ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY service_request_id
            ORDER BY updated_date DESC NULLS LAST, _ingested_at DESC
        ) AS version_rank
    FROM source

),

latest AS (

    SELECT * FROM ranked
    WHERE version_rank = 1
      AND status_description <> 'TO BE DELETED'

),

-- S5.1 Trim text, collapse repeated spaces, and turn N/A, null, None and blanks into null.
trimmed AS (

    SELECT
        service_request_id,
        -- 5.4 dates are day grain: only recent years are all midnight, so a date is the one
        -- grain that is consistent across years
        CAST(requested_date AS DATE) AS requested_date,
        CAST(updated_date AS DATE)   AS updated_date,
        CAST(closed_date AS DATE)    AS closed_date,
        status_description,
        source,
        {{ clean_text('service_name') }}       AS raw_service_name,
        {{ clean_text('agency_responsible') }} AS agency_responsible,
        {{ clean_text('comm_code') }}          AS comm_code,
        {{ clean_text('comm_name') }}          AS comm_name,
        {{ clean_text('location_type') }}      AS location_type,
        longitude,
        latitude,
        _ingested_at                           AS ingested_at
    FROM latest

),

-- S5.2 Retired services carry a leading z / Z / ZZZ / Z CT marker, or one of the words below.
-- Flag from the original name, then strip the marker.
named AS (

    SELECT
        *,
        COALESCE(
            regexp_like(raw_service_name, '^[Zz]+(\s*-\s*|\s+)')
            OR regexp_like(raw_service_name, '^ZParks\b')
            OR regexp_like(raw_service_name, '\bOLD\b|DO NOT USE|INTERNAL'),
            false
        ) AS is_legacy_service,
        regexp_replace(
            regexp_replace(raw_service_name, '^ZParks\b', 'Parks'),
            '^[Zz]+(?:\s*-\s*|\s+)', ''
        ) AS name_no_marker
    FROM trimmed

)

-- S5.3 Known prefix variants. Every remaining spelling variant is mapped to its most common
-- spelling in service_name_map.
SELECT
    service_request_id,
    requested_date,
    updated_date,
    closed_date,
    status_description,
    source,
    REGEXP_REPLACE(
        REGEXP_REPLACE(
            REGEXP_REPLACE(name_no_marker, '^Mayors Office\b', 'Mayor''s Office'),
            '^City Clerks\b', 'City Clerk''s'
        ),
        '^REDS\b', 'RE&DS'
    ) AS service_name_fixed,
    is_legacy_service,
    agency_responsible,
    comm_code,
    comm_name,
    location_type,
    longitude,
    latitude,
    ingested_at
FROM named