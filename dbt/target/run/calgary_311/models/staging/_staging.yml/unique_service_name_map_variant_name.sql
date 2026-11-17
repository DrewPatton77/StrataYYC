
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    variant_name as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_staging"."service_name_map"
where variant_name is not null
group by variant_name
having count(*) > 1



  
  
      
    ) dbt_internal_test