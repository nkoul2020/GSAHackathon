# mcp-fra-safety

A Model Context Protocol (MCP) server built with **FastMCP** and **Databricks Unity Catalog** providing governed, regulatory-accurate analytical access to **Federal Railroad Administration (FRA) 49 CFR Part 225** safety datasets and **Surface Transportation Board (STB) 49 CFR Part 1246** Class I monthly employment data.

## Regulatory & Cross-Agency Rules Enforced

- **Context-Aware Multi-Train Collision Deduplication:** Counts distinct `incidentkey` records where `jointcd = '1'` for unfiltered macro totals (preventing double-counting), while counting distinct `incidentkey` records across all `jointcd` values (`'1'`, `'2'`, `'3'`) when filtered by railroad/carrier and summing `totaldamagecost` across all involved filings.
- **Report 2.03 vs. Report 3.10 Crossing Boundaries:** Enforces `accident_type_code != '7'` for Report 2.03 and Report 1.12 train accident totals while including highway-rail crossing accidents (`include_crossings=True`) for Report 3.10.
- **Geographic Blank-Rate Rule (Report 1.12 & STB 1246):** Automatically returns `None` for Form 55 / STB 1246 system-level denominators and normalized rates whenever state, county, or city filters are active.
- **Calendar & Federal Fiscal Year Support:** Supports both Calendar Year (Jan–Dec) and Federal Fiscal Year (Oct 1 – Sep 30) across FRA forms.
- **Cross-Form & STB AAR Mark Linkage:** Walks linked incidents across Form 54 (`incidentkey`, `gxid`), Form 57 (`gradecrossingid`), Form 55a (casualties), and STB Part 1246 (`stb_1246_all_carriers`, crosswalking `CSXT` <-> `CSX`, `GTC` <-> `CN` U.S., `AMTK` <-> `ATK`).

## MCP Primitives (9 Tools, 6 Resources, 5 Prompts)

### Tools (9)
1. `get_report_1_12_rail_safety_overview` — Replicates FRA Report 1.12 overview & normalized rates across Forms 54, 55a, 57, and 55.
2. `get_train_accident_summary` — Replicates Form 54 Reports 2.03, 3.10 & 3.18 (Table 1 macro & Table 2 carrier overlap).
3. `audit_joint_track_cause_discrepancies` — Self-joins Form 54 collisions to surface conflicting cause codes & speeds across primary (`jointcd='1'`) and secondary (`jointcd IN ('2','3')`) filings.
4. `analyze_highway_rail_crossings` — Replicates Form 57 Reports 1.11, 2.08, 5.14, 5.15 & USDOT crossing hotspots.
5. `analyze_metro_corridor_safety` — Synthesizes multi-portal rail & crossing risk across metropolitan corridors.
6. `audit_delta_table_versions` — Audits Unity Catalog Delta `DESCRIBE HISTORY` governance & retroactive updates.
7. `walk_across_fra_forms` — Walks linked incidents across Forms 54, 57, and 55a.
8. `run_fra_sql_query` — Executes governed read-only cross-table SQL `SELECT`/`WITH` queries with DDL/DML blocking and truncation telemetry.
9. `analyze_class1_employment_and_safety` — Analyzes STB Part 1246 Class I headcounts (`L100`–`L600`) alongside FRA safety rates.

### Methodology Resources (6)
- `fra://reference/preparing-reports-guide` — FRA 49 CFR Part 225 report preparation rules and deduplication logic.
- `fra://reports/1.12-methodology` — Report 1.12 overview calculations and geographic blank-rate rules.
- `fra://reports/train-accidents-methodology` — Form 54 Report 2.03 vs. Report 3.10 definitions and `jointcd` rules.
- `fra://reports/form57-crossings-methodology` — Form 57 grade crossing reporting and USDOT Crossing Inventory linkage.
- `fra://reference/filter-glossary` — Standardized railroad, parent system, FRA region, SMT, and geographic filter definitions.
- `fra://reference/cause-code-categories` — FRA Appendix C primary cause code groups (`H`, `T`, `E`, `S`, `M`).

### Workflow Prompts (5)
- `metro_safety_audit_briefing` — Cross-portal metro corridor safety briefing across Forms 54, 55a, and 57.
- `railroad_system_safety_scorecard` — Normalized Report 1.12 & 3.10 parent railroad scorecard with subsidiary breakdown and joint-track audit.
- `fra_and_safety_briefing` — Cross-agency synthesis pairing FRA safety metrics with STB Part 1246 workforce trends.
- `grade_crossing_hotspot_audit` — State-level Form 57 warning device, road user, and USDOT crossing hotspot audit.
- `joint_track_discrepancy_review` — Regulatory discrepancy audit of multi-carrier Form 54 cause-code and speed mismatches.

## FRA Portal Parity & Multi-Carrier Deduplication Rules (49 CFR Part 225)

To maintain 100% numeric parity with official FRA Open Data portals (`dsuf-xcni`, `wjun-6kqb`, `9hnw-nt86`), Form 54 train accident queries dynamically adapt `jointcd` deduplication based on filter scope:

| Query Scope | SQL Deduplication Rule | Regulatory Rationale |
| :--- | :--- | :--- |
| **Unfiltered Macro Totals** *(U.S., FRA Region, State, County, City without carrier filters)* | `COUNT(DISTINCT incidentkey)` where `jointcd = '1'` | FRA assigns `jointcd = '1'` to a single primary reporting carrier per accident. Filtering to `jointcd = '1'` prevents double-counting multi-railroad collisions in macro totals. |
| **Carrier-Filtered Queries** *(`railroad_code`, `parent_railroad_code`, `railroad_class`, `railroad_group`, `smt`)* | `COUNT(DISTINCT incidentkey)` across all `jointcd` values (`'1'`, `'2'`, `'3'`) | When multiple railroads are involved in an accident, FRA may assign `jointcd = '1'` to one carrier and `'2'` or `'3'` to the others. Counting all distinct `incidentkey` rows for the filtered carrier captures every accident involving that railroad. |
| **Table 2 Carrier Breakdowns** *(`table_view="table2_railroad"`)* | `COUNT(DISTINCT incidentkey)` per reporting railroad | Displays overlapping carrier involvements across railroads. |
| **Joint-Operations Cause Audit** *(`audit_joint_track_cause_discrepancies`)* | Self-join on `incidentkey` (`p.jointcd = '1'` vs. `s.jointcd IN ('2', '3')`) | Evaluates carrier filters across both primary (`p`) and secondary (`s`) filings so discrepancies are captured regardless of which railroad received `jointcd = '1'`. |

### Verified Portal Parity Benchmark (BNSF Parent Railroad, Report 3.10)
Validated against FRA Portal `wjun-6kqb` (Report 3.10 — Train Accidents Including Highway-Rail Crossings, `parent_railroad_code = "BNSF"`):

| Calendar Year | Strict `jointcd = '1'` Only (Legacy) | All Carrier `jointcd` (`1`, `2`, `3`) (`v0.2.0-fra-parity`) | Official FRA Portal Value |
| :--- | :---: | :---: | :---: |
| **2020** | 342 | **362** | 362 |
| **2021** | 284 | **306** | **306** |
| **2022** | 367 | **382** | 382 |
| **2023** | 435 | **458** | 458 |
| **2024** | 350 | **378** | 378 |
| **2025** | 322 | **331** | 331 |

## Databricks Notebook & App Setup

1. Duplicate `.env.example` as `.env` in your Databricks Workspace folder and populate `DATABRICKS_WAREHOUSE_ID`, `DATABRICKS_CATALOG` (`FRA_CATALOG`), `DATABRICKS_SCHEMA` (`FRA_SCHEMA`), and `MCP_APP_URL`.
2. In a Databricks Notebook, install dependencies with `%pip install -r requirements.txt` and run the unit and benchmark suites:
   - `pytest -v` — Validates FastMCP server registration, tool schemas, and `fra://` methodology resources.
   - `python eval/run_eval.py` — Executes the **19-case Unity Catalog parity & security guardrail benchmark** (`eval/dataset.jsonl`) and outputs `eval/eval_report.json`.
3. In **Compute -> Apps**, attach your SQL Warehouse using resource key `sql-warehouse`, configure `app.yaml`, and deploy the repository root to serve Streamable-HTTP at `/mcp`.
4. Run `python eval/verify_live_endpoint.py` to verify end-to-end Streamable-HTTP tool execution against the live Databricks App endpoint.