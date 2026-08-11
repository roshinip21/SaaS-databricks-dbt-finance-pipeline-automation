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

---

## RevOps Module — Salesforce → Databricks → Tableau (live, built August 2026)

A second, independent analytics module lives under `revops/`. It demonstrates a
**real GTM/RevOps pipeline** — not just a dbt seed project — covering the
Customer Success, Renewals, Customer Health, and Partner ARR reporting domains
that a SaaS RevOps team owns.

### What was built

| Layer | How | Status |
|---|---|---|
| **Synthetic data** | `revops/generate_revops_data.py` — 200 customers, 15 partners, ~$17.2M ARR, deterministic (seed 42) | ✅ committed |
| **Bronze** (`gtm.bronze`) | `10_bronze_load_csv.sql` — `read_files()` from a Unity Catalog Volume; or `05_ingest_salesforce.py` for the live Salesforce path | ✅ SQL committed; run in Databricks SQL editor |
| **Silver** (`gtm.silver`) | `20_silver.sql` — type casting, contiguous ARR month spine using actual contract dates (not `date_trunc`), partner attribution flags | ✅ validated in Databricks |
| **Gold** (`gtm.gold`) | 5 marts: `gold_arr_movement`, `gold_health_scores`, `gold_renewal_pipeline`, `gold_partner_attribution`, `gold_qbr_summary` + `gold_exec_kpis` | ✅ all running in Databricks |
| **Validation** | `40_validation.sql` — RI checks, attribution invariant (sourced ≤ influenced), waterfall reconciliation, headline KPI readout | ✅ all checks passing |
| **Tableau** | 4-tab dashboard (Executive QBR, Customer Health, Renewals, Partner/Channel) connected to `gtm.gold` via native Databricks connector (extract mode) | 🔄 dashboard build in progress |
| **Cohere palette** | `revops/tableau/cohere_tableau_palette.tps` — XML preferences file (Categorical + Sequential + Diverging RAG palettes using Cohere coral `#FF7759`) | ✅ committed |

### Tableau Dashboard — 4 tabs

Connected to `gtm.gold` via Tableau's native Databricks connector (extract mode — sub-second filters, no warehouse wake cost). Cohere brand palette installed from `revops/tableau/cohere_tableau_palette.tps`.

| Tab | Source mart(s) | Key visuals |
|---|---|---|
| **Executive QBR Summary** | `gold_exec_kpis`, `gold_qbr_summary`, `gold_arr_movement` | 6 KPI tiles (ARR, net-new, NRR, GRR, renewal rate, at-risk ARR) · ARR waterfall bar+line by month · active-customers trend |
| **Customer Health & Adoption** | `gold_health_scores` | RAG distribution donut · health score vs ARR scatter (sized by ARR — surfaces "big + red" accounts) · risk driver bar by `top_driver` · LOD adoption benchmark vs segment average |
| **Renewals & Retention** | `gold_renewal_pipeline`, `gold_arr_movement` | Forward-120-day renewal timeline colored by health band · at-risk table sorted by ARR · parameter what-if ("lift renewal probability by X% → $Y impact") · NRR reproduced as a Tableau table calc |
| **Partner / Channel** | `gold_partner_attribution` | Side-by-side bars: `sourced_arr` and `influenced_arr` as **two separate bars per partner** (never stacked/summed) · contribution % of net-new ARR |

### Salesforce CRM integration & GTM initiatives

Salesforce is the **system of record** for all GTM activity. Data flows from six Salesforce objects into `gtm.bronze`, through silver transformation, and into gold marts that serve each GTM team:

| Salesforce object | GTM team served | What it drives |
|---|---|---|
| **Account** | All teams | Master dimension: segment, region, CSM owner, industry |
| **Opportunity** (with `Partner_Sourced__c`, `Partner_Influenced__c`, `Partner_Account__c` custom fields) | Partnerships, Revenue | Partner attribution (sourced vs influenced ARR), win-rate by partner, pipeline creation |
| **Contract** | CS, Finance | ARR month spine, renewal date tracking, `gold_renewal_pipeline` |
| **Case** | CS, Support | Health score input (open high-sev cases drag score); CSAT trend |
| **Campaign + CampaignMember** | Marketing | Campaign-to-renewal influence analysis — did onboarding webinar attendees churn less? |

The CSV path (`10_bronze_load_csv.sql`) and the Salesforce ingest path (`05_ingest_salesforce.py`) produce **identical bronze schemas** — silver and all five gold marts are unchanged regardless of source. Swap the bronze source at any time without touching downstream logic.

### Key modeling decisions (talking points)

- **Partner ARR: sourced vs. influenced are always separate columns, never summed.** `partner_influenced` is the superset of `partner_sourced`; adding them double-counts every sourced deal. The gold mart provides `influenced_only_arr = influenced − sourced` for safe stacking.
- **NRR/GRR computed on a fixed cohort** (accounts that existed both 12 months ago and today) — new logos added mid-year inflate NRR if excluded from the denominator.
- **ARR month spine uses actual contract dates** — `ct.start_date <= am.month AND ct.end_date > am.month` — not `date_trunc`-based joins, which silently drop contracts renewing later in the current month.
- **Databricks SQL Editor "Run All"** — multi-statement scripts (silver, gold) must be run with "Run All" (select all text first), not just "Run", which only executes the statement under the cursor.

Headline numbers from `40_validation.sql`: **$17.2M ARR · NRR ~92% · GRR ~85% · 43 renewals due in 120 days ($5.8M) · 19 Red-band accounts**

---

## How Claude was used in this project

This project was built as a **Claude Code pair-programming session** — Claude
drafted every artifact (generator, SQL scripts, Tableau guide, cheat-sheet,
palette file, documentation) while the human ran the actual Databricks SQL
editor, uploaded files to the Unity Catalog Volume, and drove Tableau. No
credentials were ever passed through chat — all secrets are environment variables.

Concrete things Claude did in this session:
- Diagnosed the Databricks MCP connector "Server URL doesn't match expected format" error and provided the correct `/api/2.0/mcp/genie/<SPACE_ID>` path.
- Wrote a deterministic, stdlib-only Python data generator with enforced referential integrity and a realistic at-risk cohort baked in.
- Designed the ARR month-spine SQL so it uses half-open contract periods (avoiding a silent $3M ARR gap that a naïve `date_trunc` join produces).
- Debugged a Databricks SQL Editor "Run" vs "Run All" confusion causing `TABLE_OR_VIEW_NOT_FOUND` errors.
- Built the Cohere brand Tableau palette as valid XML (`.tps`) — Tableau's import format, not JSON.
- Guided step-by-step execution of each script, interpreting row counts and validation output in real time.

---

## Claude API use cases for AI-driven GTM, Finance, and RevOps

Below are patterns that extend this project from a static demo to a live, AI-augmented analytics stack.

### 1. Skills / CLAUDE.md — encode team conventions as persistent AI memory

Add a `CLAUDE.md` at the repo root (or inside `revops/`) with:
- **Data model conventions**: "partner ARR is always two separate columns — never sum sourced and influenced"
- **KPI definitions**: cohort-based NRR formula, ARR spine logic, health score weights
- **SQL style guide**: preferred Spark SQL idioms, naming conventions, `date_trunc` vs actual-date joins

Every Claude Code session in this repo reads `CLAUDE.md` on startup, so any engineer or analyst working in the repo gets the same guardrails without repeating the explanation.

### 2. Natural language querying via Genie MCP

Once you create a **Genie space** over `gtm.gold` and connect it as an MCP server (URL: `https://dbc-598889e4-cffd.cloud.databricks.com/api/2.0/mcp/genie/<SPACE_ID>`), Claude can answer ad-hoc business questions directly against the live gold marts:

- *"Which Red-band accounts have renewals due in the next 60 days?"*
- *"Show me expansion ARR by CSM owner for Q2."*
- *"What's the top driver of risk for our Enterprise segment?"*

No SQL required for the business user. The Claude API's tool-calling loop routes the natural language question through Genie's text-to-SQL engine and returns the result as prose.

### 3. Autonomous renewal-risk agent

An agent using the Claude API + Databricks MCP could run on a nightly trigger and:
1. Query `gold_renewal_pipeline` for accounts newly flipped to `at_risk = true`.
2. Pull their `top_driver` from `gold_health_scores`.
3. Draft a CSM alert (Slack or email via Gmail MCP) with the account name, ARR at risk, days to renewal, and a suggested action ("schedule EBR", "engage technical success", etc.).
4. Post a summary comment on the account's renewal opportunity in Salesforce (via Salesforce MCP).

This is a direct extension of the n8n dunning workflow pattern already in the roadmap — same trigger/action structure, but Claude provides the reasoning layer that determines priority and drafts the message copy.

### 4. Automated QBR generation

At the start of each quarter, an agent can:
1. Query `gold_qbr_summary` and `gold_exec_kpis` for the trailing period.
2. Pull the partner attribution table and health distribution.
3. Draft a QBR narrative (slide-ready bullets, not raw numbers) using the Claude API.
4. Export it as a Markdown or Google Slides document for the CS/Revenue leadership review.

The gold marts are already structured to support this — every metric the QBR needs is a single-row or simple aggregate away from `gold_exec_kpis`.

### 5. Finance pipeline automation (AR/dunning)

Extending the existing n8n roadmap with Claude:
- Query `fct_ar_aging` nightly for invoices crossing 30 / 60 / 90-day buckets.
- Use the Claude API to **draft** escalation emails that are context-aware (customer segment, support history, renewal timing) rather than templated.
- A human-in-the-loop approval step (Slack approve/reject button) before emails are sent.
- Claude API's batch processing mode for high-volume invoice portfolios.

---

## Roadmap (planned — not yet built)

The pieces below are the next phases of the project. They're documented here
as the intended design; the workflow files and the `fct_ar_aging` mart they
reference are being added in later checkpoints.

### CI/CD pipeline (GitHub Actions) — finance metrics in CI

Three workflows, so the pipeline both *protects* the project and *reports* on it:

- **Pull-request checks (free, no warehouse spend):** `sqlfluff` lint →
  `dbt parse`/`compile` → **Slim CI** (`dbt build --select state:modified+`),
  so only the models a PR actually changed get built and tested. Every PR gets
  a green/red check before merge.
- **Merge to `main`:** full `dbt build` + `dbt test` against Databricks, then
  `dbt docs generate` published to GitHub Pages (browsable model lineage + docs).
- **Nightly scheduled run + finance-metrics summary:** after the nightly
  build, a CI step queries the Gold marts (`fct_mrr_monthly`, `fct_ar_aging`)
  and writes a **finance KPI summary straight into the GitHub Actions run
  summary** — current total MRR, net-new MRR, total AR outstanding, and % of
  invoices 90+ days overdue. So every pipeline run visibly reports the
  headline finance numbers, not just a pass/fail.

### n8n automation — Overdue-Invoice Dunning / Payment Reminder

A scheduled n8n workflow (or one triggered by the nightly dbt build) queries
the Databricks SQL warehouse for invoices that have just crossed into a
**30 / 60 / 90-day overdue bucket**, or whose payment **failed** (sourced from
the planned `fct_ar_aging` mart). For each one it sends a **templated
email/Slack alert** to the responsible party (the account's billing contact
plus the finance/collections team) containing the invoice number, amount, days
overdue, and a payment link.

> The same workflow pattern extends to an **Accounts-Payable** variant —
> supplier/vendor bill due-date reminders — once a vendor-bills table is added.
> (Today's data models subscription revenue, i.e. Accounts *Receivable*, so the
> alert currently targets customer invoices.)

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
