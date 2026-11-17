
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select channel
from "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
where channel is null



  
  
      
    ) dbt_internal_test