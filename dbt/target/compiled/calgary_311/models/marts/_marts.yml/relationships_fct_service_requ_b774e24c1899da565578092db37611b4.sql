
    
    

with child as (
    select agency_key as from_field
    from "awsdatacatalog"."calgary_311_dbt_marts"."fct_service_requests"
    where agency_key is not null
),

parent as (
    select agency_key as to_field
    from "awsdatacatalog"."calgary_311_dbt_marts"."dim_agency"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


