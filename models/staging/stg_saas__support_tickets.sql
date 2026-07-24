with source as (
    select * from {{ ref('support_tickets') }}
),

renamed as (
    select
        ticket_id,
        customer_id,
        cast(created_at as timestamp) as created_at,
        cast(resolved_at as timestamp) as resolved_at,
        priority,
        category,
        cast(satisfaction_score as int) as satisfaction_score,
        status as ticket_status,
        timestampdiff(hour, cast(created_at as timestamp), cast(resolved_at as timestamp)) as resolution_hours
    from source
)

select * from renamed
