with source as (
    select * from {{ ref('support_tickets') }}
),

renamed as (
    select
        ticket_id,
        customer_id,
        created_at::timestamp_ntz as created_at,
        resolved_at::timestamp_ntz as resolved_at,
        priority,
        category,
        satisfaction_score::number as satisfaction_score,
        status as ticket_status,
        datediff('hour', created_at::timestamp_ntz, resolved_at::timestamp_ntz) as resolution_hours
    from source
)

select * from renamed
