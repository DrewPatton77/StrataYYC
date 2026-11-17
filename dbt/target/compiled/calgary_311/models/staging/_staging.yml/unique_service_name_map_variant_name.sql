
    
    

select
    variant_name as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_staging"."service_name_map"
where variant_name is not null
group by variant_name
having count(*) > 1


