# SaaS Analytics (dbt + Databricks)

A self-contained dbt project with a synthetic SaaS dataset (customers,
subscriptions, billing, product usage, support tickets) loaded as dbt
seeds, plus staging/intermediate/mart models that build out a standard
SaaS analytics layer: customer 360, MRR waterfall, invoicing, product
engagement, and support metrics.

Built on **Databricks + Unity Catalog** using a medallion layout:
**Bronze** (seeds) → **Silver** (staging + intermediate) → **Gold** (marts).

## What's included

```
seeds/                      synthetic SaaS data (CSV), loaded via `dbt seed`  [BRONZE]
  plans.csv                 6 pricing plans (Starter/Pro/Enterprise x Monthly/Annual)
  customers.csv              500 customer accounts
  subscriptions.csv          663 subscription "stints" (upgrades/downgrades/churn/reactivation)
  subscription_events.csv    764 lifecycle events
  invoices.csv              9,397 monthly invoices
  payments.csv              9,215 payment attempts
  usage_events.csv         25,609 product usage events
  support_tickets.csv       1,947 support tickets

models/
  staging/          1:1 views over each seed - light renaming/casting only   [SILVER]
  intermediate/     month-spine + subscription-by-month helpers for the MRR mart
  marts/                                                                       [GOLD]
    core/            dim_customers, dim_plans, fct_subscriptions
    finance/         fct_mrr_monthly (new/expansion/contraction/churn/reactivation), fct_invoices, fct_payments
    product/         fct_usage_events, fct_usage_daily
    support/         fct_support_tickets

macros/generate_schema_name.sql   gives clean schema names (marts, staging, ...) instead of dbt's prefixed default
scripts/generate_seed_data.py     regenerates the seeds/*.csv files (deterministic, stdlib only)
databricks_setup.sql              one-time Unity Catalog catalog + schema setup
profiles.yml.example              dbt profile template (env-var driven)
```

## 1. Set up Databricks

You need three things in your Databricks workspace:

1. **A SQL Warehouse** (compute). SQL → SQL Warehouses → Create.
   - Size **2X-Small**, type **Serverless**, **Auto stop: 5 min** (keeps trial
     credit usage minimal).
   - Open it → **Connection details** and note the **Server hostname** and
     **HTTP path**.
2. **A catalog + schemas.** Open the SQL Editor, attach it to the warehouse,
   and run `databricks_setup.sql` (creates catalog `saas_analytics` and the
   layer schemas).
3. **A personal access token.** Settings → Developer → Access tokens →
   Generate. Copy it once and keep it safe — dbt uses it to authenticate.

## 2. Configure the dbt profile

Copy the example profile and point it at your workspace, either by editing
the YAML directly or exporting the referenced env vars:

```bash
mkdir -p ~/.dbt
cp profiles.yml.example ~/.dbt/profiles.yml

export SAAS_ANALYTICS_DBX_HOST='dbc-abc12345-6789.cloud.databricks.com'   # no https://
export SAAS_ANALYTICS_DBX_HTTP_PATH='/sql/1.0/warehouses/abcd1234efgh5678'
export SAAS_ANALYTICS_DBX_TOKEN='dapi...'
export SAAS_ANALYTICS_DBX_CATALOG='saas_analytics'
export SAAS_ANALYTICS_DBX_SCHEMA='dbt_dev'
```

## 3. Install the adapter, load seeds, build models

No external dbt packages are required (the month-spine logic uses Databricks'
native `sequence()` function instead of `dbt_utils`), so there's no
`dbt deps` step.

```bash
pip install dbt-databricks
dbt debug         # confirms the Databricks connection works
dbt seed          # loads seeds/*.csv into saas_analytics.seed
dbt run           # builds staging -> intermediate -> mart models
dbt test          # runs schema tests (uniqueness, not_null, relationships, accepted_values)
```

Or build everything (seeds + models + tests) in one go:

```bash
dbt build
```

## 4. Explore

Once built, the marts worth starting with (all under `saas_analytics.marts`):

- `dim_customers` - one row per customer: current plan, lifetime spend, usage, support history, active/churned status
- `fct_mrr_monthly` - one row per customer per month: `new_mrr`, `expansion_mrr`, `contraction_mrr`, `churned_mrr`, `reactivation_mrr`, and the resulting `mrr_usd` balance. Sum by month for a company-wide MRR waterfall.
- `fct_subscriptions` - one row per subscription stint (plan changes create new stints)
- `fct_invoices` / `fct_payments` - billing and collections
- `fct_usage_daily` - daily active users / event volume per customer
- `fct_support_tickets` - ticket volume, resolution time, satisfaction

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
