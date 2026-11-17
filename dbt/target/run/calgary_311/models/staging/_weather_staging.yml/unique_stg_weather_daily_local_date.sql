
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    local_date as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_staging"."stg_weather_daily"
where local_date is not null
group by local_date
having count(*) > 1



  
  
      
    ) dbt_internal_test