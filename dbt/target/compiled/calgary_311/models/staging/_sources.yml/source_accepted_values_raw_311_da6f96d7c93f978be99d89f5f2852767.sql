
    
    

with all_values as (

    select
        status_description as value_field,
        count(*) as n_records

    from "awsdatacatalog"."calgary_311"."raw_service_requests"
    group by status_description

)

select *
from all_values
where value_field not in (
    'Closed','Open','Duplicate (Closed)','Duplicate (Open)','TO BE DELETED'
)


