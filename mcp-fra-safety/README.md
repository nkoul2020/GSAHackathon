# mcp-fra-safety

A Model Context Protocol (MCP) server built with **FastMCP** and **Databricks Unity Catalog** providing governed, regulatory-accurate analytical access to **Federal Railroad Administration (FRA) 49 CFR Part 225** safety datasets and **Surface Transportation Board (STB) 49 CFR Part 1246** Class I monthly employment data.

## Regulatory & Cross-Agency Rules Enforced

- **Multi-Train Collision Deduplication:** Counts distinct `incidentkey` records where `jointcd = '1'` for macro totals while summing `totaldamagecost` across all involved railroad filings.
- **Geographic Blank-Rate Rule (Report 1.12 & STB 1246):** Automatically returns `None` for Form 55 / STB 1246 system-level denominators and normalized rates whenever state, county, or city filters are active.
- **Calendar & Federal Fiscal Year Support:** Supports both Calendar Year (Jan-Dec) and Federal Fiscal Year (Oct 1 - Sep 30) across FRA forms.
- **Cross-Form & STB AAR Mark Linkage:** Walks linked incidents across Form 54 (`incidentkey`, `gxid`), Form 57 (`gradecrossingid`), Form 55a (casualties), and STB Part 1246 (`stb_1246_all_carriers`, crosswalking `CSXT` <-> `CSX`, `GTC` <-> `CN` U.S., `AMTK` <-> `ATK`).

## MCP Primitives (9 Tools, 6 Resources, 4 Prompts)

1. `get_report_1_12_rail_safety_overview` - Replicates FRA Report 1.12 overview & normalized rates across Forms 54, 55a, 57, and 55.
2. `get_train_accident_summary` - Replicates Form 54 Reports 2.03, 3.10 & 3.18 (Table 1 macro & Table 2 carrier overlap).
3. `audit_joint_track_cause_discrepancies` - Self-joins Form 54 collisions to surface conflicting cause codes & speeds.
4. `analyze_highway_rail_crossings` - Replicates Form 57 Reports 1.11, 2.08, 5.14, 5.15 & USDOT crossing hotspots.
5. `analyze_metro_corridor_safety` - Synthesizes multi-portal rail & crossing risk across metropolitan corridors.
6. `audit_delta_table_versions` - Audits Unity Catalog Delta `DESCRIBE HISTORY` governance & retroactive updates.
7. `walk_across_fra_forms` - Walks linked incidents across Forms 54, 57, and 55a.
8. `run_fra_sql_query` - Executes governed read-only cross-table SQL `SELECT`/`WITH` queries with truncation telemetry.
9. `analyze_class1_employment_and_safety` - Analyzes STB Part 1246 Class I headcounts (`L100`-`L600`) and FRA safety rates.

## Databricks Notebook & App Setup

1. Duplicate `.env.example` as `.env` in your Databricks Workspace folder and populate `DATABRICKS_WAREHOUSE_ID`, `FRA_CATALOG`, `FRA_SCHEMA`, and `MCP_APP_URL`.
2. In a Databricks Notebook, install dependencies with `%pip install -r requirements.txt` and run `eval/run_eval.py` (`run_benchmark()`) to verify Unity Catalog parity.
3. In **Compute -> Apps**, attach your SQL Warehouse using resource key `sql-warehouse`, set `FRA_CATALOG` and `FRA_SCHEMA` in `app.yaml`, and deploy the repository root to serve Streamable-HTTP at `/mcp`.
