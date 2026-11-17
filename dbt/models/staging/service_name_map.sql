-- Maps each spelling variant of a service name to its most common spelling. Variants are names
-- that match once case and punctuation are ignored, for example "Roads - Streetlight Damage" and
-- "Roads - Streetlight - Damage". Only variants that differ from their canonical name are listed.
-- It is computed from the data on every run, so new variants are picked up automatically.
-- Ties go to the alphabetically first spelling, so the result is stable.

WITH spellings AS (

    SELECT
        service_name_fixed                                          AS variant_name,
        REGEXP_REPLACE(LOWER(service_name_fixed), '[^a-z0-9]', '')  AS match_key,
        COUNT(*)                                                    AS requests
    FROM {{ ref('base_service_requests') }}
    WHERE service_name_fixed IS NOT NULL
    GROUP BY 1, 2

),

ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY match_key
            ORDER BY requests DESC, variant_name
        ) AS spelling_rank
    FROM spellings
    WHERE match_key <> ''

),

canonical AS (

    SELECT match_key, variant_name AS canonical_name
    FROM ranked
    WHERE spelling_rank = 1

)

SELECT
    s.variant_name,
    c.canonical_name
FROM ranked s
JOIN canonical c ON c.match_key = s.match_key
WHERE s.variant_name <> c.canonical_name