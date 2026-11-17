
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    service_request_id as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_intermediate"."base_service_requests"
where service_request_id is not null
group by service_request_id
having count(*) > 1



  
  
      
    ) dbt_internal_test