-- The retired "z" marker must be gone from the service group names.
SELECT service_group, COUNT(*) AS requests
FROM {{ ref('stg_service_requests') }}
WHERE regexp_like(service_group, '^[Zz]+$')
GROUP BY 1