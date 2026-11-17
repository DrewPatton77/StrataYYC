
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select is_bulk_closure
from "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
where is_bulk_closure is null



  
  
      
    ) dbt_internal_test