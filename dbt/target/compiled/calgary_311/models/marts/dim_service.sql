-- One row per cleaned service name. The responsible agency has its own dimension (dim_agency),
-- because services change agencies when the city reorganizes. The legacy flag stays on the fact
-- table: one cleaned name can be reached through both a retired and a current spelling.
SELECT
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(service_name as varchar), ''))))) AS service_key,
    COALESCE(service_name, 'Unknown')     AS service_name,
    COALESCE(service_group, 'Unknown')    AS service_group
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
GROUP BY service_name, service_group