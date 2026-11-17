
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select status_key
from "awsdatacatalog"."calgary_311_dbt_marts"."fct_service_requests"
where status_key is null



  
  
      
    ) dbt_internal_test