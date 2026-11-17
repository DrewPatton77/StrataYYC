
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- dim_community is keyed on the code, so each code must have one name. Warn only.


SELECT comm_code, COUNT(DISTINCT comm_name) AS names
FROM "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
WHERE comm_code IS NOT NULL AND comm_name IS NOT NULL
GROUP BY 1
HAVING COUNT(DISTINCT comm_name) > 1
  
  
      
    ) dbt_internal_test