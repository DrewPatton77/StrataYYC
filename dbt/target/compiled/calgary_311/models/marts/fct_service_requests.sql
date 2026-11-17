-- One row per service request. For volume counts, filter on "not is_duplicate".
-- For time to close, use days_to_close and exclude is_bulk_closure; prefer the median.
SELECT
    service_request_id,

    (year(requested_date) * 10000 + month(requested_date) * 100 + day(requested_date))                              AS requested_date_key,
    (year(closed_date) * 10000 + month(closed_date) * 100 + day(closed_date))                                 AS closed_date_key,
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(status_description as varchar), '')))))                   AS status_key,
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(channel as varchar), '')))))                              AS channel_key,
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(service_name as varchar), '')))))                         AS service_key,
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(agency_responsible as varchar), '')))))                   AS agency_key,
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(comm_code as varchar), '')))))                            AS community_key,

    location_type,
    is_closed,
    is_duplicate,
    is_legacy_service,
    is_channel_detail_reliable,
    has_status_date_conflict,
    is_bulk_closure,
    days_to_close
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"