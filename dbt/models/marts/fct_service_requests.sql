-- One row per service request. For volume counts, filter on "not is_duplicate".
-- For time to close, use days_to_close and exclude is_bulk_closure; prefer the median.
SELECT
    service_request_id,

    {{ date_key('requested_date') }}                              AS requested_date_key,
    {{ date_key('closed_date') }}                                 AS closed_date_key,
    {{ surrogate_key(['status_description']) }}                   AS status_key,
    {{ surrogate_key(['channel']) }}                              AS channel_key,
    {{ surrogate_key(['service_name']) }}                         AS service_key,
    {{ surrogate_key(['agency_responsible']) }}                   AS agency_key,
    {{ surrogate_key(['comm_code']) }}                            AS community_key,

    location_type,
    is_closed,
    is_duplicate,
    is_legacy_service,
    is_channel_detail_reliable,
    has_status_date_conflict,
    is_bulk_closure,
    days_to_close
FROM {{ ref('stg_service_requests') }}