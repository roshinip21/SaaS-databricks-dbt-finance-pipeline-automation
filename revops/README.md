# RevOps Demo — Salesforce → Databricks → Tableau

A self-contained GTM/RevOps analytics build for the Cohere RevOps Analyst
interview. Synthetic, Salesforce-shaped data flows through a Databricks
medallion (bronze → silver → gold) into five gold marts that feed a four-tab
Tableau dashboard covering **Customer Health, Renewals, Partner ARR, and an
Executive QBR summary**.

```
Synthetic generator (Python, stdlib, deterministic)
        │  writes Salesforce-shaped CSVs (revops/data/)
        ├─────────────► Salesforce Dev org  ──simple-salesforce──┐   [REAL SOURCE]
        │               (custom fields + bulk load)              ▼
        └──► (fallback: upload CSV + COPY INTO) ──►  gtm.bronze  (Delta)
                                                          │  silver: clean + conform
                                                          ▼
                                                     gtm.silver
                                                          │  5 gold marts
                                                          ▼
                                    gtm.gold ──► Tableau (native Databricks connector, extract)
                                             ──► Genie space ──► Databricks MCP ──► Claude
```

---

## 0. Fixing the MCP connector "Server URL" error

When adding the **Databricks** connector you pasted the bare workspace URL and
got *"Server URL doesn't match expected format."* The connector does not take
the workspace root — it takes a **managed MCP server endpoint**, which is your
workspace host plus an `/api/2.0/mcp/...` path. For this workspace
(`dbc-598889e4-cffd.cloud.databricks.com`), paste **one** of:

| You want to… | Server URL to paste |
|---|---|
| **Query data with Claude** (recommended) | `https://dbc-598889e4-cffd.cloud.databricks.com/api/2.0/mcp/genie/<GENIE_SPACE_ID>` |
| Call Unity Catalog functions | `https://dbc-598889e4-cffd.cloud.databricks.com/api/2.0/mcp/functions/gtm/gold` |
| Vector search | `https://dbc-598889e4-cffd.cloud.databricks.com/api/2.0/mcp/vector-search/gtm/gold` |

**Getting a `<GENIE_SPACE_ID>`:** open (or create) a Genie space over
`gtm.gold`, then read it from the space URL — `.../genie/rooms/<GENIE_SPACE_ID>`.
Your existing "Bakehouse Sales Starter Space" works for a first connection test.

After **Continue**, you'll OAuth-authorize against the workspace, then **enable
the connector for this chat** so its tools load. (Authorization happens in your
browser — no token is ever pasted into chat.)

> **Tableau / dbt need a different value** — not the MCP URL but the SQL
> Warehouse **HTTP Path**: SQL → SQL Warehouses → your warehouse → *Connection
> details* → **HTTP path** (e.g. `/sql/1.0/warehouses/abcd1234...`), alongside
> the **Server hostname** (`dbc-598889e4-cffd.cloud.databricks.com`).

---

## 1. Quick start (guaranteed demo path — no Salesforce required)

```bash
# 1) generate the synthetic CSVs (deterministic; already committed under data/)
python3 revops/generate_revops_data.py
```

Then, in the Databricks SQL editor (GTM workspace), run in order:

| Step | File | What it does |
|---|---|---|
| 1 | `databricks/00_setup.sql` | create `gtm` catalog + bronze/silver/gold schemas + a landing Volume |
| 2 | *(upload)* | upload the 7 CSVs from `revops/data/` into `/Volumes/gtm/bronze/landing/` (Catalog Explorer → *Upload to this volume*, or the Databricks CLI — see `10_bronze_load_csv.sql`) |
| 3 | `databricks/10_bronze_load_csv.sql` | load bronze from the CSVs |
| 4 | `databricks/20_silver.sql` | clean/conform + build the ARR month spine |
| 5 | `databricks/30_gold_arr_movement.sql` | ARR waterfall |
| 6 | `databricks/31_gold_health_scores.sql` | customer health |
| 7 | `databricks/32_gold_renewal_pipeline.sql` | forward renewal book |
| 8 | `databricks/33_gold_partner_attribution.sql` | partner sourced vs influenced |
| 9 | `databricks/34_gold_qbr_summary.sql` | executive rollup + KPI snapshot |
| 10 | `databricks/40_validation.sql` | QA checks + the headline numbers to quote |

> **Free Edition can't create a catalog?** Skip the `CREATE CATALOG` line and
> replace every `gtm.` with an existing catalog you own (e.g. `workspace.`) in
> all scripts. Structure is identical.

## 2. Salesforce CRM integration & GTM initiatives

Salesforce is the **system of record** for all customer-facing GTM activity.
This pipeline pulls every object the RevOps, CS, Finance, and Partnerships teams
care about into Databricks and transforms them into the gold marts that power
the Tableau dashboard and AI agents described below.

### What data flows from Salesforce

| Salesforce object | `gtm.bronze` table | GTM purpose |
|---|---|---|
| **Account** | `bronze.accounts` | Company profile, segment, region, CSM owner — the master dimension every other table joins to |
| **Opportunity** | `bronze.opportunities` | New business, expansion, renewal pipeline; `Partner_Sourced__c` and `Partner_Influenced__c` custom fields enable partner attribution |
| **Contract** | `bronze.contracts` | ARR start/end dates, term, renewal date — drives the ARR month spine and the renewal pipeline |
| **Case** | `bronze.cases` | Support ticket volume, priority, CSAT — major input to the health score (open high-sev cases drag the score) |
| **CampaignMember** | `bronze.campaign_members` | Marketing-to-account linkage — tracks which accounts engaged with campaigns (partner co-marketing, renewal campaigns, onboarding sequences) |
| **Campaign** | `bronze.campaigns` | Campaign metadata (type, budget, influence model) |

### Custom Salesforce fields required for partner attribution

Add these to your Developer org first (`salesforce/custom_fields.md` has the click-path):

| Object | Field API name | Type | Purpose |
|---|---|---|---|
| Account | `External_Id__c` | Text, Unique, External ID | Idempotent upsert key for bulk loads |
| Opportunity | `Partner_Sourced__c` | Checkbox | Partner *created* this pipeline |
| Opportunity | `Partner_Influenced__c` | Checkbox | Partner touched this deal at any point |
| Opportunity | `Partner_Account__c` | Lookup (Account) | Which partner gets credit |

### Loading Salesforce and ingesting to Databricks

```bash
# Step 1 — add custom fields (one-time, manual in Setup or via sfdx)
# see salesforce/custom_fields.md

# Step 2 — bulk-load the synthetic CSVs into Salesforce
export SF_USERNAME='your@email.com'
export SF_PASSWORD='yourpassword'
export SF_SECURITY_TOKEN='yourtoken'
export SF_DOMAIN='login'                    # 'test' for sandbox
python3 salesforce/load_salesforce.py       # --dry-run first to validate

# Step 3 — ingest Salesforce → gtm.bronze in Databricks
# Open databricks/05_ingest_salesforce.py as a notebook and Run All.
# It reads creds from Databricks Secrets (scope: revops) — never hardcoded.
# Silver and gold scripts are unchanged — the bronze boundary is the only swap.
```

### GTM initiatives this pipeline enables

Once data flows from Salesforce through `gtm.gold`, the analytics stack supports:

**1. Customer Success — health-led renewal motion**
`gold_health_scores` combines adoption (usage trend), support (open cases, CSAT),
contract status, and engagement into a 0–100 composite score with a Green/Amber/Red
band. CSMs see their book-of-business health in Tableau and act on the `top_driver`
before a renewal is at risk — not after it's already churned.

**2. Renewals forecasting — forward 120-day pipeline**
`gold_renewal_pipeline` joins every upcoming renewal to its current health score and
computes `renewal_probability`. The Tableau parameter what-if ("lift probability by 10%
→ what's the ARR impact?") turns a static report into a live forecasting conversation
with CS leadership.

**3. Partner attribution — sourced vs. influenced (never summed)**
Salesforce's `Partner_Sourced__c` and `Partner_Influenced__c` flags flow through to
`gold_partner_attribution` as two separate dollar measures. Partners can see their
true sourced contribution without over-claiming the influenced superset. A critical
RevOps data quality control: if these are ever summed into one "partner ARR" number,
every sourced deal is double-counted.

**4. Marketing campaign influence analysis**
`bronze.campaign_members` links accounts to campaigns. Silver joins this to renewal
and health data, enabling questions like "did accounts that attended the onboarding
webinar have lower churn?" — a marketing-to-CS feedback loop.

**5. Executive QBR — automated narrative from live data**
`gold_exec_kpis` is a single row of pre-computed cohort-based NRR, GRR, at-risk ARR,
and partner contribution %. At quarter-end, a Claude API agent can query this table
and draft QBR slide bullets automatically (see Claude use cases in the root README).

### Real pipeline (optional upgrade — the stronger interview story)

Populate your empty Salesforce Developer org and ingest it live:

1. `salesforce/custom_fields.md` — add the partner-attribution custom fields.
2. `python3 salesforce/load_salesforce.py` — bulk-load the CSVs into Salesforce
   (creds via env vars; see the file header).
3. `databricks/05_ingest_salesforce.py` — run as a Databricks notebook to pull
   Salesforce → `gtm.bronze` (replaces step 3 above). Silver/gold are unchanged.

---

## Tableau Dashboard — 4 tabs on `gtm.gold`

**Connect:** Tableau Desktop → Connect → To a Server → Databricks.
Server hostname: `dbc-598889e4-cffd.cloud.databricks.com` · HTTP path: from SQL Warehouses → Connection details.
Auth: Personal Access Token (Settings → Developer → Access tokens).
Catalog `gtm` · Schema `gold`. Switch each data source to **Extract** (not Live) — the gold marts are small and nightly-refreshed; an extract makes every filter sub-second and avoids warehouse wake latency.

---

### Tab 1 — Executive QBR Summary

**Sources:** `gold_exec_kpis` (single KPI row) + `gold_qbr_summary` (monthly rollup) + `gold_arr_movement`

**What it shows:**

| Visual | Fields | Notes |
|---|---|---|
| KPI tiles (6 one-number sheets) | `total_arr`, `net_new_arr_12m`, `nrr`, `grr`, `renewal_rate_12m`, `at_risk_arr` | Format NRR/GRR/renewal as % |
| ARR waterfall bar+line | `month` on Columns; `new_arr`, `expansion_arr`, `contraction_arr`, `churned_arr`, `reactivation_arr` as Measure Values bars; `ending_arr` as a dual-axis line | Greens for new/expansion, reds for contraction/churn |
| Active customers trend | `active_customers` by `month` (line) | Spot logo churn visually |

**Talking point:** NRR and GRR are **cohort-based** — measured only on accounts that existed both 12 months ago and today. New logos excluded from the denominator so mid-year growth doesn't inflate retention.

---

### Tab 2 — Customer Health & Adoption

**Source:** `gold_health_scores`

| Visual | Fields | Notes |
|---|---|---|
| RAG donut / stacked bar | `health_band` on Color, Count of accounts | Sort Red first; use Cohere Diverging RAG palette |
| Health scatter | `health_score` (x) vs `current_arr` (y), colored by `health_band`, sized by `current_arr` | Surfaces "big + red" accounts — highest ARR protection priority |
| Risk driver bar | Count by `top_driver` | Shows whether risk is adoption, usage decline, support, or engagement |

**LOD calc (cohort adoption benchmark):**
```
{ FIXED [segment] : AVG([adoption_pct]) }
```
Subtract from `[adoption_pct]` → over/under-adoption vs. segment peers. This requires a Level-of-Detail expression because the segment average is at a coarser grain than the account row.

**Tooltip on scatter:** account name, segment, CSM owner, `top_driver`, `health_score`.

---

### Tab 3 — Renewals & Retention

**Sources:** `gold_renewal_pipeline` + `gold_arr_movement`

| Visual | Fields | Notes |
|---|---|---|
| Renewal timeline bars | `renewal_date` on Columns, `arr_up_for_renewal` height, colored by `health_band` | Mart is pre-filtered to next-120-day window |
| At-risk table | Account, `renewal_date`, `days_to_renewal`, `arr_up_for_renewal`, `health_score`, `renewal_probability`, `at_risk` | Sort by `arr_up_for_renewal` desc; conditional format `at_risk = true` rows in red |
| What-if parameter | Parameter `Prob Adjustment` (float, −0.3 → +0.3) drives: `forecast = arr_up_for_renewal * MIN(1, MAX(0, renewal_probability + [Prob Adjustment]))` | "If we lift renewal probability by 10%, what's the revenue impact?" — live interactive moment |
| NRR table calc | `WINDOW_SUM` of (expansion + contraction + churn) over trailing 12 months ÷ starting ARR from `gold_arr_movement` | Reproduces `gold_exec_kpis.nrr` as a table calc — demonstrates you can do it either way |

---

### Tab 4 — Partner / Channel

**Source:** `gold_partner_attribution`

| Visual | Fields | Notes |
|---|---|---|
| Side-by-side bars | `partner_name` on Rows; `sourced_arr` and `influenced_arr` as two separate bars (Measure Names on Columns) | **Never stacked** — influenced is the superset of sourced; summing = double-count |
| Safe stack (alternative) | `sourced_arr` + `influenced_only_arr` = `influenced_arr` | Mart provides `influenced_only_arr = influenced − sourced` for this exact case |
| Contribution % | `pct_of_net_new_sourced` and `pct_of_net_new_influenced` | Shows each partner's share of company net-new ARR |

**Critical modeling rule:** `partner_influenced ⊇ partner_sourced`. "Sourced" = partner *created* the pipeline. "Influenced" = partner *touched* the deal at any point. These answer different questions and are always two separate bars, never one "partner ARR" number.

---

### Gold mart → Tableau tab mapping

| Gold mart | Feeds tab | Headline measures |
|---|---|---|
| `gold_exec_kpis` | Executive QBR (KPI tiles) | total ARR, NRR, GRR, renewal rate, at-risk ARR |
| `gold_qbr_summary` | Executive QBR (waterfall + trend) | new/expansion/contraction/churn/reactivation ARR by month |
| `gold_arr_movement` | Executive QBR + Renewals (table calc) | monthly ARR waterfall at account grain |
| `gold_health_scores` | Customer Health | health score 0–100, RAG band, top driver, adoption % |
| `gold_renewal_pipeline` | Renewals & Retention | ARR up for renewal, days-to-renewal, renewal probability, at-risk |
| `gold_partner_attribution` | Partner / Channel | sourced ARR, influenced ARR, influenced-only ARR, contribution % |

See `tableau/dashboard_build_guide.md` for the field-by-field drag-and-drop instructions.

## Headline numbers in this dataset (from `40_validation.sql`)

| Metric | Value |
|---|---|
| Total current ARR | ~$17.2M |
| Net-new ARR (TTM) | ~$3.5M |
| NRR / GRR (cohort, TTM) | ~92% / ~85% |
| Renewal rate (TTM) | ~83% |
| Renewals due next 120 days | 43 accounts · ~$5.8M (7 at-risk · ~$0.7M) |
| Partner sourced / influenced ARR | ~$4.2M / ~$9.9M |
| Customers by health | 82 Green · 61 Amber · 19 Red |

## Tableau palette (Cohere branding)

`tableau/cohere_tableau_palette.tps` is a Tableau preferences XML file with three
Cohere-branded color palettes:

| Palette | Type | Use for |
|---|---|---|
| **Cohere Categorical** | Regular | dimension coloring (RAG bands, segments, partners) |
| **Cohere Sequential** | Ordered-sequential | heat maps, choropleth, single-measure gradient |
| **Cohere Diverging RAG** | Ordered-diverging | health scores (red → neutral → teal), vs-target variance |

Primary brand color: **coral `#FF7759`** · Near-black `#212121` · Teal `#5EC8C2`.

**Install:** copy (or move) `cohere_tableau_palette.tps` to your Tableau
repository preferences file, then restart Tableau Desktop:

- **Mac:** `~/Documents/My Tableau Repository/Preferences.tps`
- **Windows:** `C:\Users\<you>\Documents\My Tableau Repository\Preferences.tps`

If `Preferences.tps` already exists, open it and paste the three `<color-palette>`
blocks inside the existing `<preferences>` element.

---

## Current build status (August 2026)

| Artifact | Status |
|---|---|
| Synthetic data (7 CSVs) | ✅ committed under `revops/data/` |
| `gtm` catalog + schemas + landing Volume | ✅ created in Databricks (`00_setup.sql`) |
| Bronze Delta tables (7 tables) | ✅ loaded from CSVs |
| Silver tables (7 tables, including ARR month spine) | ✅ all OK per verification query |
| Gold marts (5 tables + `gold_exec_kpis`) | ✅ running in `gtm.gold` |
| Validation checks | ✅ all passing (sourced ≤ influenced, waterfall reconciles, RI clean) |
| Tableau connection to `gtm.gold` | ✅ connected (extract mode) |
| 4-tab Tableau dashboard | 🔄 build in progress (drag-and-drop per `dashboard_build_guide.md`) |
| Cohere palette installed in Tableau | 🔄 copy `.tps` file and restart |
| Salesforce custom fields + bulk load | ⬜ optional (Phase 2) — CSV path gives an identical demo |
| Genie space + Databricks MCP connector | ⬜ optional (Phase 3) — enables natural-language querying |

---

## How Claude was used to build this

This entire module was built in a single **Claude Code** pair-programming session.
Claude drafted every file; the human ran the Databricks SQL editor, uploaded CSVs
to the Volume, and drove Tableau. No credentials were ever passed through chat.

Key moments where Claude caught or fixed real issues:

| Problem | Root cause | Fix |
|---|---|---|
| ARR waterfall $14.17M vs $17.22M | Silver spine used `date_trunc('month', end_date)` — dropped Aug-2026 renewals that started mid-month | Changed to `ct.start_date <= am.month AND ct.end_date > am.month` (actual dates) |
| `TABLE_OR_VIEW_NOT_FOUND: account_month_arr` | Databricks SQL Editor "Run" only runs the statement under the cursor, not all statements | Added 7-row OK/MISSING verification at end of `20_silver.sql`; always use "Run All" |
| Databricks MCP "Server URL doesn't match expected format" | Connector needs `/api/2.0/mcp/genie/<ID>` path, not the bare workspace URL | Documented paste-ready URLs in § 0 above |
| Tableau Data Source Error after PAT revoke | A live token was accidentally shared in chat (immediately revoked); Tableau still referenced it | Generate new PAT; update Databricks connection in Tableau → "Edit Connection" |

---

## Regenerating the data

`revops/generate_revops_data.py` is deterministic (fixed seed, stdlib only). The
`AS_OF` anchor is `2026-08-01`; if you change it, update the matching
`DATE'2026-08-01'` literals in `20_silver.sql` and `34_gold_qbr_summary.sql`.
