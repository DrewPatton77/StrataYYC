SELECT DISTINCT
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(status_description as varchar), ''))))) AS status_key,
    status_description,
    is_closed,
    is_duplicate
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"