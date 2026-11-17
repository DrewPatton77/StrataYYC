
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select variant_name
from "awsdatacatalog"."calgary_311_dbt_staging"."service_name_map"
where variant_name is null



  
  
      
    ) dbt_internal_test