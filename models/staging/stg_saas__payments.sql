with source as (
    select * from {{ ref('payments') }}
),

renamed as (
    select
        payment_id,
        invoice_id,
        customer_id,
        cast(payment_date as date) as payment_date,
        cast(amount_usd as decimal(10, 2)) as amount_usd,
        payment_method,
        status as payment_status
    from source
)

select * from renamed
