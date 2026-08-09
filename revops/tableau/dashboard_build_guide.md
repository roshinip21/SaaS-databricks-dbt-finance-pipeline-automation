# Tableau Build Guide — 4-Tab RevOps Dashboard

Build target: a four-tab workbook on the Databricks `gtm.gold` marts. Claude
Code can't drive Tableau, so this is a manual build — but the gold tables are
shaped so each tab is mostly drag-and-drop.

## Connect to Databricks

1. Tableau Desktop → **Connect → To a Server → Databricks**.
2. **Server hostname:** `dbc-598889e4-cffd.cloud.databricks.com`
   **HTTP Path:** SQL Warehouses → your warehouse → *Connection details → HTTP path*.
   **Auth:** Personal Access Token (Settings → Developer → Access tokens), or OAuth.
3. Catalog `gtm`, Schema `gold`. Add each `gold_*` table as its own data source
   (they're already aggregated to the grain each tab needs — no joins required
   for the core views).
4. **Use an Extract, not Live.** Click the toggle to **Extract** on each source.
   These marts are small and static; an extract makes the dashboard instant and
   avoids waking the warehouse on every filter. (Talking point below.)

---

## Tab 1 — Executive QBR Summary  (`gold_qbr_summary`, `gold_exec_kpis`)

**KPI tiles** (from `gold_exec_kpis`, a single row): drop `total_arr`,
`net_new_arr_12m`, `nrr`, `grr`, `renewal_rate_12m`, `at_risk_arr` onto separate
one-number worksheets. Format `nrr`/`grr`/`renewal_rate_12m` as %.

**ARR waterfall trend** (from `gold_qbr_summary`): `month` on Columns; build a
Measure Values bar of `new_arr`, `expansion_arr`, `contraction_arr`,
`churned_arr`, `reactivation_arr`. Color by measure name (greens for
new/expansion, reds for contraction/churn). Add `ending_arr` as a line on a dual
axis for the running balance.

**Active customers** line: `active_customers` by `month`.

---

## Tab 2 — Customer Health & Adoption  (`gold_health_scores`)

**RAG distribution:** `health_band` on Color (Green/Amber/Red), `Count` of
accounts — a stacked bar or donut. Sort Red first.

**Health scatter:** `health_score` (x) vs `current_arr` (y), one mark per
account, colored by `health_band`, sized by `current_arr`. This surfaces the
"big + red" accounts to protect. Tooltip: account, segment, CSM, `top_driver`.

**Drivers breakdown:** bar of `Count` by `top_driver` — shows whether risk is
adoption, usage decline, support, or engagement.

**LOD example (cohort adoption):** to compare an account's adoption to its
segment average, add a calc:
```
{ FIXED [segment] : AVG([adoption_pct]) }
```
then `[adoption_pct] - segment_avg` shows over/under-adoption vs peers. (LOD
because the benchmark is at a coarser grain than the row.)

---

## Tab 3 — Renewals & Retention  (`gold_renewal_pipeline`, `gold_arr_movement`)

**Renewal timeline:** `renewal_date` on Columns, `arr_up_for_renewal` bars,
colored by `health_band`. Filter is implicit (mart is already next-120-days).

**At-risk table:** rows = account; columns = `renewal_date`, `days_to_renewal`,
`arr_up_for_renewal`, `health_score`, `renewal_probability`, `at_risk`. Sort by
`arr_up_for_renewal` desc; highlight `at_risk = true`.

**Parameter-driven what-if:** create a parameter `Prob Adjustment` (float,
-0.3…+0.3). Calc:
```
forecast = [arr_up_for_renewal]
         * MIN(1, MAX(0, [renewal_probability] + [Prob Adjustment]))
```
SUM(forecast) is a live "what if we lift renewal probability by X" number — a
clean interactive moment in the interview.

**NRR/GRR table calc:** from `gold_arr_movement`, a running retention view:
`WINDOW_SUM` of (expansion+contraction+churn) over trailing 12 months divided by
starting ARR reproduces NRR as a table calc (the `gold_exec_kpis` row is the
precomputed version — show both to prove you can do it either way).

---

## Tab 4 — Partner / Channel  (`gold_partner_attribution`)

**THE key modeling point — do not sum sourced and influenced.**
`partner_influenced` is the superset of `partner_sourced`, so adding
`sourced_arr + influenced_arr` double-counts every sourced deal.

**Side-by-side bars (correct):** `partner_name` on Rows; put `sourced_arr` and
`influenced_arr` as **two separate bars** using Measure Names on Columns (a
*side-by-side* bar, not a stacked one). Two honest, comparable bars per partner.

**If you must stack**, stack `sourced_arr` + `influenced_only_arr` (the mart
provides `influenced_only_arr = influenced − sourced`), which totals to
`influenced_arr` without double-counting.

**Contribution:** `pct_of_net_new_sourced` and `pct_of_net_new_influenced` show
each partner's share of company net-new ARR.

---

## Two talking points the tabs are designed to earn

- **Extract vs. Live:** Extract for a static, fast dashboard on a serverless
  warehouse (no per-interaction warehouse spend, sub-second filters); Live only
  when you need up-to-the-minute data and can accept warehouse wake latency. For
  a QBR dashboard on nightly-refreshed marts, Extract is right.
- **Sourced vs. influenced:** two different questions ("who *created* this
  pipeline" vs "who *helped*"), two disjoint-at-the-headline measures, never one
  summed "partner ARR" number — that's how partner teams inflate credit.
