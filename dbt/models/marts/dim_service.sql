-- One row per cleaned service name. The responsible agency has its own dimension (dim_agency),
-- because services change agencies when the city reorganizes. The legacy flag stays on the fact
-- table: one cleaned name can be reached through both a retired and a current spelling.
SELECT
    {{ surrogate_key(['service_name']) }} AS service_key,
    COALESCE(service_name, 'Unknown')     AS service_name,
    COALESCE(service_group, 'Unknown')    AS service_group
FROM {{ ref('stg_service_requests') }}
GROUP BY service_name, service_group