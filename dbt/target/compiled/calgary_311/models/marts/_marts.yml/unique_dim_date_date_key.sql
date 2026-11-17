
    
    

select
    date_key as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_marts"."dim_date"
where date_key is not null
group by date_key
having count(*) > 1


