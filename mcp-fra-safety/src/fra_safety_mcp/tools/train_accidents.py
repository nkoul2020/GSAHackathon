from typing import Any, Dict, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_form54_filters, build_time_predicate, resolve_year_expr


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_train_accident_summary(
        start_year: int = 2016,
        end_year: int = 2025,
        year_type: str = "calendar",
        include_crossings: bool = False,
        table_view: str = "table1_macro",
        group_by: str = "cause_group",
        railroad_code: Optional[str] = None,
        parent_railroad_code: Optional[str] = None,
        railroad_class: Optional[str] = None,
        railroad_group: Optional[str] = None,
        fra_region: Optional[str] = None,
        smt: Optional[str] = None,
        state: Optional[str] = None,
        county: Optional[str] = None,
        city: Optional[str] = None,
        accident_type: Optional[str] = None,
        cause_category: Optional[str] = None,
        cause_code_prefix: Optional[str] = None,
        track_type: Optional[str] = None,
        track_class: Optional[str] = None,
        method_of_operation: Optional[str] = None,
        hazmat_only: bool = False,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Replicates FRA Form 54 Train Accident Reports (portal wjun-6kqb) from Unity Catalog:
        - include_crossings=False -> Report 2.03 (Train Accidents Not at Crossings)
        - include_crossings=True  -> Report 3.10 (Train Accidents Including Crossings)
        - table_view='table1_macro'    -> Deduplicated macro totals (jointcd='1' when unfiltered; all carrier incidents when filtered by railroad)
        - table_view='table2_railroad' -> Overlapping involvement counts per railroad
        """
        params: Dict[str, Any] = {}
        safe_limit = max(1, min(int(limit), 500))

        try:
            c54 = get_table_columns(config.form_54_table)
            inc_col = resolve_col(c54, "f", ("incident_key", "accident_number"))
            jcd_col = resolve_col(c54, "f", ("joint_cd", "joint_code"))
            dmg_col = resolve_col(c54, "f", ("total_damage_cost", "equipment_damage_cost"), fallback_sql="0")
            k_col = resolve_col(c54, "f", ("total_persons_killed", "total_killed_form54"), fallback_sql="0")
            i_col = resolve_col(c54, "f", ("total_persons_injured", "total_injured_form54"), fallback_sql="0")
            haz_col = resolve_col(c54, "f", ("hazmat_cars_damaged", "hazmat_cars_damaged_derailed"), fallback_sql="0")
            cau_col = resolve_col(c54, "f", ("primary_accident_cause_code", "accident_cause_code"), fallback_sql="'M000'")

            t54 = build_time_predicate(
                c54, "f", "t54", params,
                ("year", "accident_year", "year4", "iyr"), ("accident_month", "imo", "month"), ("date",),
                start_year, end_year, year_type,
            )
            f54_common = build_common_filters(
                c54, "f", "c54", params, True, state, county, city, fra_region, smt,
                railroad_code, parent_railroad_code, railroad_class, railroad_group,
            )
            f54_spec = build_form54_filters(
                c54, "f", "s54", params,
                include_crossings=include_crossings,
                accident_type=accident_type,
                cause_category=cause_category,
                cause_code_prefix=cause_code_prefix,
                track_type=track_type,
                track_class=track_class,
                method_of_operation=method_of_operation,
                hazmat_only=hazmat_only,
            )

            gb = group_by.strip().lower()
            if gb == "cause_group":
                dim_expr = f"""
                CASE UPPER(SUBSTRING(TRIM(CAST({cau_col} AS STRING)), 1, 1))
                    WHEN 'H' THEN 'H - Human Factors'
                    WHEN 'T' THEN 'T - Track, Roadbed & Structures'
                    WHEN 'E' THEN 'E - Mechanical & Electrical Failures'
                    WHEN 'S' THEN 'S - Signal & Communication'
                    ELSE 'M - Miscellaneous Causes'
                END
                """
                dim_alias = "cause_group"
            elif gb == "cause_code":
                desc_col = resolve_col(c54, "f", ("primary_accident_cause", "accident_cause"), fallback_sql="''")
                dim_expr = f"CONCAT(UPPER(TRIM(CAST({cau_col} AS STRING))), ' - ', COALESCE(CAST({desc_col} AS STRING), ''))"
                dim_alias = "cause_code"
            elif gb == "accident_type":
                typ_col = resolve_col(c54, "f", ("accident_type", "accident_type_code"), fallback_sql="'Unknown'")
                dim_expr = f"COALESCE(NULLIF(TRIM(CAST({typ_col} AS STRING)), ''), 'Unknown')"
                dim_alias = "accident_type"
            elif gb == "track_type":
                trk_col = resolve_col(c54, "f", ("track_type", "track_type_code"), fallback_sql="'Unknown'")
                dim_expr = f"COALESCE(NULLIF(TRIM(CAST({trk_col} AS STRING)), ''), 'Unknown')"
                dim_alias = "track_type"
            elif gb == "railroad":
                rr_col = resolve_col(c54, "f", ("reporting_railroad_code", "railroad_code"), fallback_sql="'UNK'")
                rrn_col = resolve_col(c54, "f", ("reporting_railroad_name", "railroad_name"), fallback_sql="''")
                dim_expr = f"CONCAT(UPPER(TRIM(CAST({rr_col} AS STRING))), ' - ', COALESCE(CAST({rrn_col} AS STRING), ''))"
                dim_alias = "railroad"
            elif gb == "state":
                st_col = resolve_col(c54, "f", ("state_abbr", "state_name", "state_code"), fallback_sql="'UNK'")
                dim_expr = f"UPPER(TRIM(CAST({st_col} AS STRING)))"
                dim_alias = "state"
            else:
                dim_expr = resolve_year_expr(c54, "f", ("year", "accident_year", "year4", "iyr"), ("date",))
                dim_alias = "year"

            is_table2 = table_view.strip().lower() in ("table2_railroad", "table2", "railroad_overlap")
            has_carrier_filter = any([
                railroad_code,
                parent_railroad_code,
                railroad_class,
                railroad_group,
                smt,
            ])

            if is_table2 or has_carrier_filter:
                count_expr = f"COUNT(DISTINCT {inc_col})"
            else:
                count_expr = f"COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' THEN {inc_col} END)"

            order_clause = "1 ASC" if dim_alias == "year" else "accident_count DESC, total_damage_cost DESC"

            q_total = f"""
            SELECT
                {count_expr} AS deduplicated_grand_total_accidents,
                COUNT(DISTINCT {inc_col}) AS total_railroad_involvements,
                COALESCE(SUM(CAST({dmg_col} AS DOUBLE)), 0) AS total_damage_cost,
                COALESCE(SUM(CAST({k_col} AS INT)), 0) AS total_fatalities,
                COALESCE(SUM(CAST({i_col} AS INT)), 0) AS total_injuries,
                COALESCE(SUM(CAST({haz_col} AS INT)), 0) AS hazmat_cars_damaged
            FROM {config.fq_table(config.form_54_table)} f
            WHERE {t54} {f54_common} {f54_spec}
            """

            q_breakdown = f"""
            SELECT
                {dim_expr} AS {dim_alias},
                {count_expr} AS accident_count,
                COALESCE(SUM(CAST({dmg_col} AS DOUBLE)), 0) AS total_damage_cost,
                COALESCE(SUM(CAST({k_col} AS INT)), 0) AS fatalities,
                COALESCE(SUM(CAST({i_col} AS INT)), 0) AS injuries,
                COALESCE(SUM(CAST({haz_col} AS INT)), 0) AS hazmat_cars_damaged
            FROM {config.fq_table(config.form_54_table)} f
            WHERE {t54} {f54_common} {f54_spec}
            GROUP BY 1
            ORDER BY {order_clause}
            LIMIT {safe_limit}
            """

            grand_total = execute_query(q_total, params)[0]
            breakdown = execute_query(q_breakdown, params)
            report_label = (
                "FRA Report 3.10 - Train Accidents Including Highway-Rail Crossings"
                if include_crossings
                else "FRA Report 2.03 - Train Accidents Not at Highway-Rail Crossings"
            )

            return {
                "report": report_label,
                "portal_reference": "https://data.transportation.gov/stories/s/wjun-6kqb",
                "table_view": (
                    "table2_railroad (overlapping carrier counts)"
                    if is_table2
                    else ("table1_macro (carrier-filtered distinct incidents)" if has_carrier_filter else "table1_macro (jointcd='1' deduplicated)")
                ),
                "group_by": dim_alias,
                "grand_total": grand_total,
                "breakdown": breakdown,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}
