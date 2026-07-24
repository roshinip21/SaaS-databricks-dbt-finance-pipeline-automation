with source as (
    select * from {{ ref('invoices') }}
),

renamed as (
    select
        invoice_id,
        customer_id,
        subscription_id,
        cast(invoice_date as date) as invoice_date,
        cast(due_date as date) as due_date,
        cast(period_start as date) as period_start,
        cast(period_end as date) as period_end,
        cast(amount_usd as decimal(10, 2)) as amount_usd,
        status as invoice_status
    from source
)

select * from renamed
