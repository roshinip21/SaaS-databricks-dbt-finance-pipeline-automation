-- Daily engagement rollup per customer: active users and event volume,
-- handy for DAU/WAU-style product analytics.
select
    customer_id,
    event_date,
    count(distinct user_id) as active_users,
    count(*) as event_count,
    count(distinct event_name) as distinct_event_types
from {{ ref('stg_saas__usage_events') }}
group by 1, 2
