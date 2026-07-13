with source as (
    select * from {{ ref('payments') }}
),

renamed as (
    select
        payment_id,
        invoice_id,
        customer_id,
        payment_date::date as payment_date,
        amount_usd::number(10, 2) as amount_usd,
        payment_method,
        status as payment_status
    from source
)

select * from renamed
