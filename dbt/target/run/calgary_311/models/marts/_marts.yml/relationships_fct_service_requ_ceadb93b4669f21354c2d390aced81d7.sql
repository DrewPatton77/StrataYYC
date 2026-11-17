
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with child as (
    select closed_date_key as from_field
    from "awsdatacatalog"."calgary_311_dbt_marts"."fct_service_requests"
    where closed_date_key is not null
),

parent as (
    select date_key as to_field
    from "awsdatacatalog"."calgary_311_dbt_marts"."dim_date"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null



  
  
      
    ) dbt_internal_test