# Changelog

All notable changes to `mcp-fra-safety` are documented in this file.

## [v0.2.0-fra-parity] - 2026-11-23

### Fixed
- **Carrier-Filtered Incident Deduplication (`train_accidents.py`, `report_1_12.py`):** Updated Form 54 accident count expressions so `jointcd = '1'` is enforced only on unfiltered macro queries (`U.S.`, `FRA Region`, `State`, `County`, `City`). When any carrier-level filter (`railroad_code`, `parent_railroad_code`, `railroad_class`, `railroad_group`, or `smt`) is active, queries now compute `COUNT(DISTINCT incidentkey)` across all `jointcd` values (`'1'`, `'2'`, `'3'`), restoring exact parity with FRA Reports 1.12, 2.03, and 3.10 (e.g., BNSF CY 2021 Report 3.10 = `306`).
- **Joint-Track Cause Discrepancy Audit (`joint_cause_audit.py`):**
  - Expanded carrier filters (`railroad_code`, `parent_railroad_code`) to match both primary (`jointcd = '1'`) and secondary (`jointcd IN ('2', '3')`) filings so multi-carrier incidents are not dropped when the queried railroad is assigned `jointcd = '2'` or `'3'`.
  - Added `jointcd = '3'` (track maintenance / additional equipment filings) and `joint_track_type` to discrepancy outputs.
  - Added null/empty guards on Appendix C cause codes and `SELECT DISTINCT` deduplication.
- **Chronological Year Sorting (`train_accidents.py`):** Ordered `group_by="year"` results chronologically (`1 ASC`) rather than sorting by descending accident count.
- **Zero-Padded Code Matching (`report_1_12.py`):** Matched both single-digit (`'1'`–`'6'`) and zero-padded (`'01'`–`'06'`) string codes for `accident_type_code` and `track_type_code`.

## [v0.1.0-baseline] - 2026-11-23

### Added
- Initial working FastMCP Dataset Access Server (`mcp-fra-safety`) deployed on Databricks Apps (`mcp-nk-test`) backed by Unity Catalog (`users.neeraj_koul.form_54_accidents`, `form_55a_casualties`, `form_55_operational`, `form_57_crossings`).
- Core MCP tools (`get_report_1_12_rail_safety_overview`, `get_train_accident_summary`, `audit_joint_track_cause_discrepancies`, `analyze_highway_rail_crossings`, `analyze_metro_corridor_safety`, `audit_delta_table_versions`, `cross_form_query`, `stb_employment`), `fra://` regulatory resources, investigation prompts, evaluation harness, and submission PDF generator.
