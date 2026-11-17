
    
    

select
    service_request_id as unique_field,
    count(*) as n_records

from "awsdatacatalog"."calgary_311_dbt_staging"."stg_service_requests"
where service_request_id is not null
group by service_request_id
having count(*) > 1


