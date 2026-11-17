-- One row per channel. Use channel_group (App or Other channels) for trends across all years;
-- the full channel split is only reliable before March 2021 (see is_channel_detail_reliable).
SELECT DISTINCT
    {{ surrogate_key(['channel']) }} AS channel_key,
    COALESCE(channel, 'Unknown')     AS channel,
    channel_group
FROM {{ ref('stg_service_requests') }}