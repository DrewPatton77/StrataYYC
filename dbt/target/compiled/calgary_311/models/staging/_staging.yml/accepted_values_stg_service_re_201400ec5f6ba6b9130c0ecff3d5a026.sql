
    
    

with all_values as (

    select
        status_description as value_field,
        count(*) as n_records

    from "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
    group by status_description

)

select *
from all_values
where value_field not in (
    'Closed','Open','Duplicate (Closed)','Duplicate (Open)'
)


