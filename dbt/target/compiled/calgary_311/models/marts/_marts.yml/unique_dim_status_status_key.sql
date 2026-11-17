
    
    

select
    status_key as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_marts"."dim_status"
where status_key is not null
group by status_key
having count(*) > 1


