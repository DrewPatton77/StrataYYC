
    
    

select
    channel_key as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_marts"."dim_channel"
where channel_key is not null
group by channel_key
having count(*) > 1


