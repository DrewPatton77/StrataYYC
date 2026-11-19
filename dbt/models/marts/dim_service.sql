-- One row per cleaned service name. The responsible agency has its own dimension (dim_agency),
-- because services change agencies when the city reorganizes. The legacy flag stays on the fact
-- table: one cleaned name can be reached through both a retired and a current spelling.
-- reporting_group and reporting_group_name are stable across the City's renames (see service_group_map).
-- Use them for trends over time. Groups not in the map keep their own name.
WITH services AS (

    SELECT service_name, service_group
    FROM {{ ref('stg_service_requests') }}
    GROUP BY service_name, service_group

)

SELECT
    {{ surrogate_key(['s.service_name']) }}                              AS service_key,
    COALESCE(s.service_name, 'Unknown')                                  AS service_name,
    COALESCE(s.service_group, 'Unknown')                                 AS service_group,
    COALESCE(m.reporting_group, s.service_group, 'Unknown')              AS reporting_group,
    COALESCE(m.reporting_group_name, s.service_group, 'Unknown')         AS reporting_group_name
FROM services s
LEFT JOIN {{ ref('service_group_map') }} m
    ON m.service_group = s.service_group