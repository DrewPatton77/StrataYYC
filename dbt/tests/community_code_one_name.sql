-- dim_community is keyed on the code, so each code must have one name. Warn only.
{{ config(severity='warn') }}

SELECT comm_code, COUNT(DISTINCT comm_name) AS names
FROM {{ ref('stg_service_requests') }}
WHERE comm_code IS NOT NULL AND comm_name IS NOT NULL
GROUP BY 1
HAVING COUNT(DISTINCT comm_name) > 1