with invoices as (
    select * from {{ ref('stg_saas__invoices') }}
),

payments as (
    select
        invoice_id,
        sum(case when payment_status = 'succeeded' then amount_usd else 0 end) as amount_collected_usd,
        max(payment_date) as last_payment_date
    from {{ ref('stg_saas__payments') }}
    group by 1
)

select
    i.invoice_id,
    i.customer_id,
    i.subscription_id,
    i.invoice_date,
    i.due_date,
    i.period_start,
    i.period_end,
    i.amount_usd,
    i.invoice_status,
    coalesce(p.amount_collected_usd, 0) as amount_collected_usd,
    p.last_payment_date,
    datediff('day', i.due_date, coalesce(p.last_payment_date, current_date())) as days_past_due
from invoices i
left join payments p on i.invoice_id = p.invoice_id
