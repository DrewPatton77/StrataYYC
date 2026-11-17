
    
    

with all_values as (

    select
        source as value_field,
        count(*) as n_records

    from "awsdatacatalog"."calgary_311"."raw_service_requests"
    group by source

)

select *
from all_values
where value_field not in (
    'Phone','Web','Other','App'
)


