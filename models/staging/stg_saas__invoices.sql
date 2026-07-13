with source as (
    select * from {{ ref('invoices') }}
),

renamed as (
    select
        invoice_id,
        customer_id,
        subscription_id,
        invoice_date::date as invoice_date,
        due_date::date as due_date,
        period_start::date as period_start,
        period_end::date as period_end,
        amount_usd::number(10, 2) as amount_usd,
        status as invoice_status
    from source
)

select * from renamed
