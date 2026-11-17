-- One row per channel. Use channel_group (App or Other channels) for trends across all years;
-- the full channel split is only reliable before March 2021 (see is_channel_detail_reliable).
SELECT DISTINCT
    to_hex(md5(to_utf8(concat_ws('|', coalesce(cast(channel as varchar), ''))))) AS channel_key,
    COALESCE(channel, 'Unknown')     AS channel,
    channel_group
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"