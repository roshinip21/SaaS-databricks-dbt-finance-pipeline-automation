-- fct_mrr_monthly's movement columns must always reconcile to the month's
-- ending MRR balance. Returns offending rows (test fails if any are returned).
select *
from {{ ref('fct_mrr_monthly') }}
where mrr_usd != prior_mrr_usd + new_mrr + reactivation_mrr + expansion_mrr + contraction_mrr + churned_mrr
