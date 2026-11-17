
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select service_request_id
from "awsdatacatalog"."calgary_311"."raw_service_requests"
where service_request_id is null



  
  
      
    ) dbt_internal_test