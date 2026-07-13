select
    p.payment_id,
    p.invoice_id,
    p.customer_id,
    p.payment_date,
    p.amount_usd,
    p.payment_method,
    p.payment_status,
    i.invoice_status,
    i.subscription_id
from {{ ref('stg_saas__payments') }} p
left join {{ ref('stg_saas__invoices') }} i on p.invoice_id = i.invoice_id
