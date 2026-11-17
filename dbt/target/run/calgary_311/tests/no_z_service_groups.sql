
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- The retired "z" marker must be gone from the service group names.
SELECT service_group, COUNT(*) AS requests
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
WHERE regexp_like(service_group, '^[Zz]+$')
GROUP BY 1
  
  
      
    ) dbt_internal_test