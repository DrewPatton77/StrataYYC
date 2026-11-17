
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        channel_group as value_field,
        count(*) as n_records

    from "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
    group by channel_group

)

select *
from all_values
where value_field not in (
    'App','Other channels'
)



  
  
      
    ) dbt_internal_test