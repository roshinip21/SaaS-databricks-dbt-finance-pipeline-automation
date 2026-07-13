select
    e.event_id,
    e.customer_id,
    e.user_id,
    e.event_name,
    e.feature_area,
    e.event_timestamp,
    e.event_date,
    c.tier as customer_tier
from {{ ref('stg_saas__usage_events') }} e
left join {{ ref('fct_subscriptions') }} c
    on e.customer_id = c.customer_id and c.is_current
