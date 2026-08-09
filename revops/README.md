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

## 2. Real pipeline (optional upgrade — the stronger interview story)

Populate your empty Salesforce Developer org and ingest it live:

1. `salesforce/custom_fields.md` — add the partner-attribution custom fields.
2. `python3 salesforce/load_salesforce.py` — bulk-load the CSVs into Salesforce
   (creds via env vars; see the file header).
3. `databricks/05_ingest_salesforce.py` — run as a Databricks notebook to pull
   Salesforce → `gtm.bronze` (replaces step 3 above). Silver/gold are unchanged.

---

## The 5 gold marts → the 4 Tableau tabs

| Gold mart | Feeds tab | Headline measures |
|---|---|---|
| `gold_qbr_summary` + `gold_exec_kpis` | **Executive QBR** | total ARR, net-new ARR, NRR, GRR, renewal rate |
| `gold_health_scores` | **Customer Health & Adoption** | health score, RAG band, top driver |
| `gold_renewal_pipeline` | **Renewals & Retention** | ARR up for renewal, days-to-renewal, at-risk, renewal probability |
| `gold_partner_attribution` | **Partner / Channel** | sourced ARR vs influenced ARR (side-by-side, never summed) |
| `gold_arr_movement` | Executive QBR + Renewals | new / expansion / contraction / churn / reactivation |

See `tableau/dashboard_build_guide.md` for the field-by-field build.

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

## Regenerating the data

`revops/generate_revops_data.py` is deterministic (fixed seed, stdlib only). The
`AS_OF` anchor is `2026-08-01`; if you change it, update the matching
`DATE'2026-08-01'` literals in `20_silver.sql` and `34_gold_qbr_summary.sql`.
