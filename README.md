# SaaS Analytics (dbt + Snowflake)

A self-contained dbt project with a synthetic SaaS dataset (customers,
subscriptions, billing, product usage, support tickets) loaded as dbt
seeds, plus staging/intermediate/mart models that build out a standard
SaaS analytics layer: customer 360, MRR waterfall, invoicing, product
engagement, and support metrics.

## What's included

```
seeds/                      synthetic SaaS data (CSV), loaded via `dbt seed`
  plans.csv                 6 pricing plans (Starter/Pro/Enterprise x Monthly/Annual)
  customers.csv              500 customer accounts
  subscriptions.csv          663 subscription "stints" (upgrades/downgrades/churn/reactivation)
  subscription_events.csv    764 lifecycle events
  invoices.csv              9,397 monthly invoices
  payments.csv              9,215 payment attempts
  usage_events.csv         25,609 product usage events
  support_tickets.csv       1,947 support tickets

models/
  staging/          1:1 views over each seed - light renaming/casting only
  intermediate/     month-spine + subscription-by-month helpers for the MRR mart
  marts/
    core/            dim_customers, dim_plans, fct_subscriptions
    finance/         fct_mrr_monthly (new/expansion/contraction/churn/reactivation), fct_invoices, fct_payments
    product/         fct_usage_events, fct_usage_daily
    support/         fct_support_tickets

scripts/generate_seed_data.py   regenerates the seeds/*.csv files (deterministic, stdlib only)
snowflake_setup.sql             one-time Snowflake warehouse/db/schema/role setup
profiles.yml.example            dbt profile template (env-var driven)
```

## 1. Set up Snowflake

Run `snowflake_setup.sql` in Snowflake (as `ACCOUNTADMIN` or an equivalent
role) to create the warehouse, database, schemas, a dedicated role, and a
service user. Edit the placeholder password before running.

This creates:
- Warehouse `SAAS_ANALYTICS_WH` (XSMALL, auto-suspend)
- Database `SAAS_ANALYTICS` with schemas `SEED`, `DBT_DEV`, `DBT_PROD`
- Role `SAAS_ANALYTICS_ROLE` and user `SAAS_ANALYTICS_SVC`

Feel free to rename anything — just keep the profile in step 2 consistent.

## 2. Configure the dbt profile

Copy the example profile and point it at your Snowflake account, either by
editing the YAML directly or exporting the referenced env vars:

```bash
mkdir -p ~/.dbt
cp profiles.yml.example ~/.dbt/profiles.yml

export SAAS_ANALYTICS_SF_ACCOUNT=xy12345.us-east-1
export SAAS_ANALYTICS_SF_USER=saas_analytics_svc
export SAAS_ANALYTICS_SF_PASSWORD='...'
export SAAS_ANALYTICS_SF_ROLE=SAAS_ANALYTICS_ROLE
export SAAS_ANALYTICS_SF_WAREHOUSE=SAAS_ANALYTICS_WH
export SAAS_ANALYTICS_SF_DATABASE=SAAS_ANALYTICS
export SAAS_ANALYTICS_SF_SCHEMA=DBT_DEV
```

## 3. Install dependencies, load seeds, build models

No external dbt packages are required (the month-spine logic uses Snowflake's
native `GENERATOR` table function instead of `dbt_utils`), so there's no
`dbt deps` step.

```bash
pip install dbt-snowflake
dbt debug         # confirms the Snowflake connection works
dbt seed          # loads seeds/*.csv into SAAS_ANALYTICS.SEED
dbt run           # builds staging -> intermediate -> mart models
dbt test          # runs schema tests (uniqueness, not_null, relationships, accepted_values)
```

Or build everything (seeds + models + tests) in one go:

```bash
dbt build
```

## 4. Explore

Once built, the marts worth starting with:

- `marts.dim_customers` - one row per customer: current plan, lifetime spend, usage, support history, active/churned status
- `marts.fct_mrr_monthly` - one row per customer per month: `new_mrr`, `expansion_mrr`, `contraction_mrr`, `churned_mrr`, `reactivation_mrr`, and the resulting `mrr_usd` balance. Sum by month for a company-wide MRR waterfall.
- `marts.fct_subscriptions` - one row per subscription stint (plan changes create new stints)
- `marts.fct_invoices` / `marts.fct_payments` - billing and collections
- `marts.fct_usage_daily` - daily active users / event volume per customer
- `marts.fct_support_tickets` - ticket volume, resolution time, satisfaction

## Regenerating the seed data

The seeds are produced by `scripts/generate_seed_data.py`, a dependency-free
Python script with a fixed random seed (deterministic output). To change
volume or shape (e.g. more customers, different churn rates), edit the
constants near the top of the script and rerun:

```bash
python3 scripts/generate_seed_data.py
```

This overwrites the CSVs in `seeds/`; rerun `dbt seed --full-refresh`
afterward.
