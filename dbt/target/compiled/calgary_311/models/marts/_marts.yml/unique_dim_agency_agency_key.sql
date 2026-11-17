
    
    

select
    agency_key as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_marts"."dim_agency"
where agency_key is not null
group by agency_key
having count(*) > 1


