from typing import Any, Dict, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_time_predicate, resolve_year_expr


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def audit_joint_track_cause_discrepancies(
        start_year: int = 2016,
        end_year: int = 2025,
        year_type: str = "calendar",
        state: Optional[str] = None,
        railroad_code: Optional[str] = None,
        parent_railroad_code: Optional[str] = None,
        only_mismatched_causes: bool = True,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Self-joins Form 54 multi-railroad collisions on `incidentkey` (`jointcd = '1'` vs `'2'`)
        in Unity Catalog to surface conflicting Appendix C primary cause codes and reported train
        speeds between the primary and secondary railroads involved in the same accident.
        """
        params: Dict[str, Any] = {}
        safe_limit = max(1, min(int(limit), 200))

        try:
            c54 = get_table_columns(config.form_54_table)
            inc_col = resolve_col(c54, "p", ("incident_key", "accident_number"))
            inc_sec = resolve_col(c54, "s", ("incident_key", "accident_number"))
            jcd_p = resolve_col(c54, "p", ("joint_cd", "joint_code"))
            jcd_s = resolve_col(c54, "s", ("joint_cd", "joint_code"))

            rr_p = resolve_col(c54, "p", ("reporting_railroad_code", "railroad_code"))
            rr_s = resolve_col(c54, "s", ("reporting_railroad_code", "railroad_code"))
            cau_p = resolve_col(c54, "p", ("primary_accident_cause_code", "accident_cause_code"))
            cau_s = resolve_col(c54, "s", ("primary_accident_cause_code", "accident_cause_code"))
            desc_p = resolve_col(c54, "p", ("primary_accident_cause", "accident_cause"), fallback_sql="''")
            desc_s = resolve_col(c54, "s", ("primary_accident_cause", "accident_cause"), fallback_sql="''")
            spd_p = resolve_col(c54, "p", ("train_speed", "recorded_estimated_speed"), fallback_sql="NULL")
            spd_s = resolve_col(c54, "s", ("train_speed", "recorded_estimated_speed"), fallback_sql="NULL")
            dmg_p = resolve_col(c54, "p", ("total_damage_cost", "equipment_damage_cost"), fallback_sql="0")
            dmg_s = resolve_col(c54, "s", ("total_damage_cost", "equipment_damage_cost"), fallback_sql="0")
            st_p = resolve_col(c54, "p", ("state_abbr", "state_name", "state_code"), fallback_sql="''")
            city_p = resolve_col(c54, "p", ("station", "city_name"), fallback_sql="''")
            dt_p = resolve_col(c54, "p", ("date",), fallback_sql="''")
            yr_p = resolve_year_expr(c54, "p", ("year", "accident_year", "year4", "iyr"), ("date",))

            t54 = build_time_predicate(
                c54, "p", "t54", params,
                ("year", "accident_year", "year4", "iyr"), ("accident_month", "imo", "month"), ("date",),
                start_year, end_year, year_type,
            )
            f54_common = build_common_filters(
                c54, "p", "c54", params, True, state, None, None, None, None,
                railroad_code, parent_railroad_code, None, None,
            )

            mismatch_clause = (
                f"AND UPPER(TRIM(CAST({cau_p} AS STRING))) != UPPER(TRIM(CAST({cau_s} AS STRING)))"
                if only_mismatched_causes
                else ""
            )

            fq = config.fq_table(config.form_54_table)
            q = f"""
            SELECT
                {inc_col} AS incident_key,
                {yr_p} AS year,
                CAST({dt_p} AS STRING) AS date,
                UPPER(TRIM(CAST({st_p} AS STRING))) AS state,
                TRIM(CAST({city_p} AS STRING)) AS nearest_city_town,
                UPPER(TRIM(CAST({rr_p} AS STRING))) AS primary_railroad,
                UPPER(TRIM(CAST({cau_p} AS STRING))) AS primary_cause_code,
                CAST({desc_p} AS STRING) AS primary_cause_desc,
                CAST({spd_p} AS DOUBLE) AS primary_reported_speed_mph,
                UPPER(TRIM(CAST({rr_s} AS STRING))) AS secondary_railroad,
                UPPER(TRIM(CAST({cau_s} AS STRING))) AS secondary_cause_code,
                CAST({desc_s} AS STRING) AS secondary_cause_desc,
                CAST({spd_s} AS DOUBLE) AS secondary_reported_speed_mph,
                (COALESCE(CAST({dmg_p} AS DOUBLE), 0) + COALESCE(CAST({dmg_s} AS DOUBLE), 0)) AS combined_damage_cost
            FROM {fq} p
            INNER JOIN {fq} s
                ON {inc_col} = {inc_sec}
                AND TRIM(CAST({jcd_p} AS STRING)) = '1'
                AND TRIM(CAST({jcd_s} AS STRING)) = '2'
            WHERE {t54} {f54_common} {mismatch_clause}
            ORDER BY combined_damage_cost DESC
            LIMIT {safe_limit}
            """

            rows = execute_query(q, params)
            return {
                "audit_type": "49 CFR Part 225 Joint-Operations Cause & Speed Discrepancy Audit",
                "only_mismatched_causes": only_mismatched_causes,
                "records_returned": len(rows),
                "discrepancies": rows,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}