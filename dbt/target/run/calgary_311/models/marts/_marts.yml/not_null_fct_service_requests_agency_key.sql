
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select agency_key
from "awsdatacatalog"."calgary_311_dbt_marts"."fct_service_requests"
where agency_key is null



  
  
      
    ) dbt_internal_test