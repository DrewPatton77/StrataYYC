
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- About 880 requests have a location type but no coordinates (0.01%). They can still be counted
-- by community. Warn only, so a jump is visible.


SELECT service_request_id, location_type
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
WHERE location_type IS NOT NULL AND (latitude IS NULL OR longitude IS NULL)
  
  
      
    ) dbt_internal_test