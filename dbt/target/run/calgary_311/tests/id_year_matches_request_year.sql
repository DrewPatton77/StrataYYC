
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- The two-digit year in a request ID should match its request year. One known exception:
-- 13-00221829, requested in 2012. Warn only.


SELECT service_request_id, requested_date
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
WHERE TRY_CAST(substr(service_request_id, 1, 2) AS INTEGER) <> YEAR(requested_date) % 100
  
  
      
    ) dbt_internal_test