-- One row per responsible agency. The prefix is the department code (for example CS, TRAN, UEP).
-- Agencies are renamed over time, so the same service can appear under more than one agency.
SELECT
    {{ surrogate_key(['agency_responsible']) }}          AS agency_key,
    COALESCE(agency_responsible, 'Unknown')               AS agency_name,
    COALESCE(split_part(agency_responsible, ' - ', 1), 'Unknown') AS agency_prefix
FROM {{ ref('stg_service_requests') }}
GROUP BY agency_responsible