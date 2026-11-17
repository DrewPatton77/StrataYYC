
    
    

select
    service_key as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_marts"."dim_service"
where service_key is not null
group by service_key
having count(*) > 1


