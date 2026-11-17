
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select local_date
from "awsdatacatalog"."calgary_311_dbt_staging"."stg_weather_daily"
where local_date is null



  
  
      
    ) dbt_internal_test