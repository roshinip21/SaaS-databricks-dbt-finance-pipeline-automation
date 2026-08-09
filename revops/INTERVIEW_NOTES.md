# Interview Cheat-Sheet — Cohere RevOps Analyst (Analytics)

45 min with Ting Li. JD is **Customer Success, Renewals, Customer Health, and
Partner/Partner-ARR reporting** — not sales pipeline. This build maps 1:1 to
those four areas. Below: the 60-second pitch, a demo script, the four concepts
to speak fluently on, and the numbers to have memorized.

## 60-second pitch
"I built the RevOps stack the JD describes end to end: synthetic
Salesforce-shaped GTM data → Databricks medallion (bronze/silver/gold) →
Tableau. Five gold marts drive a four-tab dashboard — Executive QBR, Customer
Health, Renewals, and Partner ARR. The whole thing runs on Databricks Free
Edition and Tableau, and I can walk you through both the modeling decisions and
the SQL."

## Demo script (tab by tab)
1. **Executive QBR** — "Top line: ~$17.2M ARR, ~$3.5M net-new this year, NRR 92%,
   GRR 85%. The waterfall shows *why* ARR moved — expansion vs contraction vs
   churn — not just that it did."
2. **Customer Health** — "Every active account scored 0–100 from adoption, usage
   trend, support, and engagement, banded Red/Amber/Green. The scatter of health
   vs ARR finds the *big-and-red* accounts — that's the CSM worklist. 19 reds
   right now."
3. **Renewals** — "43 renewals worth $5.8M in the next 120 days; 7 at-risk worth
   ~$0.7M. Probability is health-driven, and this parameter lets us model
   'what if we lift renewal probability 10 points.'"
4. **Partner ARR** — "Sourced vs influenced, side by side — deliberately never
   summed. More on that in a second."

## The four concepts to nail

### 1. Sourced vs. influenced partner ARR — *never summed*
- **Sourced** = the partner *created* the deal (originated pipeline).
- **Influenced** = the partner *touched* the deal (helped, but didn't originate).
- Influenced is the **superset** — every sourced deal is also influenced. So
  `sourced + influenced` **double-counts** every sourced dollar. That's how
  partner teams accidentally (or conveniently) inflate their number.
- Report them as **two separate measures**, side-by-side bars. If a stacked
  total is needed, stack `sourced` + `influenced_only` (= influenced − sourced).
- In this data: **$4.2M sourced, $9.9M influenced** — I keep them in separate
  columns in `gold_partner_attribution` and never add them.

### 2. NRR is the compounding metric
- **NRR** = (starting ARR + expansion − contraction − churn) ÷ starting ARR, on
  the **cohort that existed 12 months ago** (new logos excluded from the ratio).
  **GRR** is the same without expansion — it's the floor, capped at 100%.
- Why it's *the* metric: NRR compounds. 120% NRR doubles revenue from the
  existing base in ~4 years with zero new logos; <100% means you're leaking and
  every new sale first backfills churn.
- Read *this* dataset honestly: **NRR 92% (< 100)** means the base is contracting
  net of expansion — the story is "expansion isn't yet outrunning churn +
  downgrades; the lever is the at-risk renewal book and driving expansion in
  Green accounts." Being able to *diagnose* a soft number beats quoting a rosy one.
- GRR 85% / gross churn 11% tells you how much is pure loss vs. downgrade.

### 3. Medallion (bronze → silver → gold) — why
- **Bronze** = raw, source-shaped, append-only (Salesforce objects as-is). You
  can always re-derive everything from it; it's your audit trail.
- **Silver** = cleaned, typed, conformed, business rules applied (e.g. the
  partner sourced/influenced logic, the ARR month spine).
- **Gold** = aggregated, dashboard-ready marts at the grain the BI tool needs.
- Payoff I built for on purpose: **the source is swappable at the bronze
  boundary.** CSV load or live Salesforce ingest both produce identical
  `gtm.bronze.*`, so silver/gold — and Tableau — never change. That's the
  governance + maintainability argument for medallion in one sentence.

### 4. Tableau Extract vs. Live
- **Extract**: a snapshot in Tableau's engine. Fast, no warehouse spend per
  interaction, great for dashboards on data that refreshes on a schedule.
- **Live**: queries Databricks on every interaction — up-to-the-minute, but
  slower and wakes the serverless warehouse (latency + cost).
- For a **QBR dashboard on nightly-built gold marts → Extract**, refreshed after
  the nightly job. Live only when minutes-fresh data is worth the cost.

## Likely questions → crisp answers
- *"How do you define an at-risk renewal?"* Renewal due in the window with a Red
  band or health < 45; I'd tune the threshold against actual churn outcomes.
- *"Why Databricks over a warehouse?"* Unity Catalog governance, one platform for
  ELT + BI serving + (here) an MCP/Genie natural-language layer, and Delta so
  bronze is replayable.
- *"How would you productionize this?"* Nightly job builds gold; schedule the
  Salesforce ingest; add tests (row counts, `sourced ≤ influenced`, waterfall
  reconciliation — I already run these in `40_validation.sql`); Tableau extract
  refresh after the job.
- *"What would you add next?"* Cohort retention curves (LOD), a churn-risk model
  on the health features, and per-CSM/segment QBR filters.

## Numbers to memorize
| Metric | Value |
|---|---|
| Total ARR | ~$17.2M |
| Net-new ARR (TTM) | ~$3.5M |
| NRR / GRR | 92% / 85% |
| Renewal rate (TTM) | 83% |
| Renewals next 120d | 43 accts · $5.8M (7 at-risk · $0.7M) |
| Partner sourced / influenced | $4.2M / $9.9M (never summed) |
| Health | 82 Green · 61 Amber · 19 Red |
