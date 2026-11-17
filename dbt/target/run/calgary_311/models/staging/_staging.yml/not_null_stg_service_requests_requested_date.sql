
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select requested_date
from "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
where requested_date is null



  
  
      
    ) dbt_internal_test