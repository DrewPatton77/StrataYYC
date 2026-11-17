-- Service names that match once case and punctuation are ignored. Fix by regenerating
-- service_name_map from the notebook. Warn only: a new variant can arrive with new data.
{{ config(severity='warn') }}

SELECT
    REGEXP_REPLACE(LOWER(service_name), '[^a-z0-9]', '') AS match_key,
    COUNT(distinct service_name)                         AS spellings
FROM {{ ref('stg_service_requests') }}
WHERE service_name IS NOT NULL
GROUP BY 1
HAVING COUNT(distinct service_name) > 1