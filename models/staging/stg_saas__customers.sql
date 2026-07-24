with source as (
    select * from {{ ref('customers') }}
),

renamed as (
    select
        customer_id,
        company_name,
        industry,
        country,
        cast(employee_count as int) as employee_count,
        acquisition_channel,
        cast(signup_date as date) as signup_date
    from source
)

select * from renamed
