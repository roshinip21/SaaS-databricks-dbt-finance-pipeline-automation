with source as (
    select * from {{ ref('customers') }}
),

renamed as (
    select
        customer_id,
        company_name,
        industry,
        country,
        employee_count::number as employee_count,
        acquisition_channel,
        signup_date::date as signup_date
    from source
)

select * from renamed
