SELECT DISTINCT
    {{ surrogate_key(['status_description']) }} AS status_key,
    status_description,
    is_closed,
    is_duplicate
FROM {{ ref('stg_service_requests') }}
