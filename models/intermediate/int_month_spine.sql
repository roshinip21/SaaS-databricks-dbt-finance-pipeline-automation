{{
    config(materialized='ephemeral')
}}

-- Calendar-month spine from 2023-01 through the current month, generated
-- natively with Snowflake's GENERATOR (no external package dependency).
with generated as (
    select
        dateadd(month, seq4(), to_date('2023-01-01')) as date_month
    from table(generator(rowcount => 120))
)

select date_month
from generated
where date_month <= dateadd(month, 1, date_trunc('month', current_date()))
