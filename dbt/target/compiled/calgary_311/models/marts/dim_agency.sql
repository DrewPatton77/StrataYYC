-- One row per responsible agency. The prefix is the department code (for example CS, TRAN, UEP).
-- Agencies are renamed over time, so the same service can appear under more than one agency.
SELECT
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(agency_responsible as varchar), '')))))          AS agency_key,
    COALESCE(agency_responsible, 'Unknown')               AS agency_name,
    COALESCE(split_part(agency_responsible, ' - ', 1), 'Unknown') AS agency_prefix
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
GROUP BY agency_responsible