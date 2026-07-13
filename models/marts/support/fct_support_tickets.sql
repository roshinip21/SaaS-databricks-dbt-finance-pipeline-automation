select
    t.ticket_id,
    t.customer_id,
    t.created_at,
    t.resolved_at,
    t.priority,
    t.category,
    t.satisfaction_score,
    t.ticket_status,
    t.resolution_hours,
    c.tier as customer_tier
from {{ ref('stg_saas__support_tickets') }} t
left join {{ ref('fct_subscriptions') }} c
    on t.customer_id = c.customer_id and c.is_current
