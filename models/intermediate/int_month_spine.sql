{{
    config(materialized='ephemeral')
}}

-- Calendar-month spine from 2023-01 through the current month, generated
-- natively with Databricks' sequence() + explode (no external package).
-- sequence(start, stop, step) builds an array of month-start dates; explode
-- turns that array into one row per month.
select explode(
    sequence(
        to_date('2023-01-01'),
        add_months(date_trunc('MONTH', current_date()), 1),
        interval 1 month
    )
) as date_month
