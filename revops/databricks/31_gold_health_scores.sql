-- ===========================================================================
-- 31_gold_health_scores.sql  --  Composite customer health (0-100 + RAG)
-- ===========================================================================
-- One row per ACTIVE customer. The score is an explainable, weighted composite
-- so you can defend every point in the interview:
--   adoption   (0-40)  feature adoption % of the latest usage month
--   trend      (0-15)  active-user momentum: last 3 mo vs prior 3 mo
--   support    (0-25)  starts at 25; open high-sev cases and low CSAT subtract
--   engagement (0-20)  active users relative to the customer's own peak
-- RAG: >=70 Green, 40-69 Amber, <40 Red. top_driver = weakest component.
-- ===========================================================================

CREATE OR REPLACE TABLE gtm.gold.gold_health_scores AS
WITH latest_usage AS (
    SELECT account_id, feature_adoption_pct, active_users,
           row_number() OVER (PARTITION BY account_id ORDER BY usage_month DESC) AS rn
    FROM gtm.silver.usage_monthly
),
adoption AS (
    SELECT account_id, feature_adoption_pct AS adoption_pct, active_users AS latest_users
    FROM latest_usage WHERE rn = 1
),
peak AS (
    SELECT account_id, max(active_users) AS peak_users
    FROM gtm.silver.usage_monthly GROUP BY account_id
),
trend AS (   -- avg active users last 3 months vs the 3 before that
    SELECT account_id,
           avg(CASE WHEN rn <= 3 THEN active_users END)               AS recent_users,
           avg(CASE WHEN rn BETWEEN 4 AND 6 THEN active_users END)    AS prior_users
    FROM latest_usage
    GROUP BY account_id
),
support AS (
    SELECT account_id,
           sum(CASE WHEN is_open AND is_high_priority THEN 1 ELSE 0 END) AS open_high_sev,
           avg(CASE WHEN closed_at >= DATE'2026-08-01' - INTERVAL 90 DAYS
                    THEN csat END)                                       AS avg_csat_90d
    FROM gtm.silver.cases
    GROUP BY account_id
),
scored AS (
    SELECT
        ac.account_id, ac.account_name, ac.segment, ac.industry, ac.region,
        ac.csm_owner, ac.current_arr,
        coalesce(ad.adoption_pct, 0)              AS adoption_pct,
        t.recent_users, t.prior_users,
        coalesce(s.open_high_sev, 0)              AS open_high_sev,
        s.avg_csat_90d,
        -- component scores -----------------------------------------------
        round(coalesce(ad.adoption_pct, 0) * 40, 1)                        AS adoption_component,
        CASE
            WHEN t.prior_users IS NULL OR t.prior_users = 0 THEN 8.0
            WHEN t.recent_users >= t.prior_users * 1.05 THEN 15.0
            WHEN t.recent_users >= t.prior_users * 0.95 THEN 9.0
            WHEN t.recent_users >= t.prior_users * 0.80 THEN 4.0
            ELSE 0.0
        END                                                                 AS trend_component,
        greatest(0.0, 25.0
            - coalesce(s.open_high_sev, 0) * 8.0
            - CASE WHEN s.avg_csat_90d IS NOT NULL AND s.avg_csat_90d < 3
                   THEN (3 - s.avg_csat_90d) * 5 ELSE 0 END)                AS support_component,
        round(least(1.0, coalesce(ad.latest_users, 0)
              / nullif(p.peak_users, 0)) * 20, 1)                          AS engagement_component
    FROM gtm.silver.account_current ac
    LEFT JOIN adoption ad ON ad.account_id = ac.account_id
    LEFT JOIN trend    t  ON t.account_id  = ac.account_id
    LEFT JOIN peak     p  ON p.account_id  = ac.account_id
    LEFT JOIN support  s  ON s.account_id  = ac.account_id
    WHERE ac.is_active
)
SELECT
    *,
    round(adoption_component + trend_component + support_component
          + engagement_component, 1)                          AS health_score,
    CASE
        WHEN adoption_component + trend_component + support_component
             + engagement_component >= 70 THEN 'Green'
        WHEN adoption_component + trend_component + support_component
             + engagement_component >= 40 THEN 'Amber'
        ELSE 'Red'
    END                                                        AS health_band,
    -- weakest component, normalized to its max, becomes the headline driver
    CASE least(
            adoption_component  / 40.0,
            trend_component     / 15.0,
            support_component   / 25.0,
            engagement_component / 20.0)
        WHEN adoption_component   / 40.0 THEN 'Low feature adoption'
        WHEN trend_component      / 15.0 THEN 'Declining usage'
        WHEN support_component    / 25.0 THEN 'Support / CSAT risk'
        ELSE 'Low engagement'
    END                                                        AS top_driver
FROM scored;
