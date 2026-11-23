from typing import Any, Dict, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_form54_filters, build_time_predicate

_FRA_TO_STB_MARK: Dict[str, str] = {
    "CSX": "CSXT", "CSXT": "CSXT",
    "CN": "GTC", "GTW": "GTC", "IC": "GTC", "WC": "GTC", "GTC": "GTC",
    "ATK": "AMTK", "AMTK": "AMTK",
    "CPKC": "CPKC", "CP": "CPKC", "SOO": "SOO", "KCS": "KCS",
    "BNSF": "BNSF", "NS": "NS", "UP": "UP",
}

_STB_TO_FRA_PARENT: Dict[str, str] = {
    "CSXT": "CSX", "GTC": "CN", "AMTK": "ATK",
    "CPKC": "CPKC", "SOO": "CPKC", "KCS": "CPKC",
    "BNSF": "BNSF", "NS": "NS", "UP": "UP",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def analyze_class1_employment_and_safety(
        start_year: int = 2020,
        end_year: int = 2025,
        railroad_code: Optional[str] = None,
        sub_measure_prefix: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Queries STB Part 1246 Class I monthly employment and cross-links FRA Part 225 safety rates
        params: Dict[str, Any] = {}
        raw_rr = railroad_code.strip().upper() if railroad_code else None
        stb_mark = _FRA_TO_STB_MARK.get(raw_rr, raw_rr) if raw_rr else None
        fra_parent = _STB_TO_FRA_PARENT.get(stb_mark, stb_mark) if stb_mark else None

        try:
            cstb = get_table_columns(config.stb_1246_table)
            aar_col = resolve_col(cstb, "e", ("railroad_aar_reporting_mark", "railroad_reporting_aar_mark", "aar_mark"))
            end_dt_col = resolve_col(cstb, "e", ("report_period_end_date", "report_period_start_date"))
            yr_col = resolve_col(cstb, "e", ("report_year",), fallback_sql="NULL")
            mo_col = resolve_col(cstb, "e", ("report_month",), fallback_sql="NULL")
            meas_col = resolve_col(cstb, "e", ("measure_name", "measure_name_analytics"), fallback_sql="'Employees mid-month'")
            sub_col = resolve_col(cstb, "e", ("sub_measure", "sub_measure_name"), fallback_sql="'ALL'")
            line_col = resolve_col(cstb, "e", ("report_line_number", "pk_compilation_line_number"), fallback_sql="''")
            val_col = resolve_col(cstb, "e", ("fact_value", "value"))

            dt_expr = f"COALESCE(TRY_CAST({end_dt_col} AS DATE), TO_DATE(CAST({end_dt_col} AS STRING), 'MM/dd/yyyy'))"
            yr_expr = f"COALESCE(TRY_CAST({yr_col} AS INT), YEAR({dt_expr}))"
            mo_expr = f"COALESCE(TRY_CAST({mo_col} AS INT), MONTH({dt_expr}))"
            num_val = f"TRY_CAST(REPLACE(CAST({val_col} AS STRING), ',', '') AS DOUBLE)"

            params["stb_sy"], params["stb_ey"] = int(start_year), int(end_year)
            where_clauses = [
                f"{yr_expr} BETWEEN %(stb_sy)s AND %(stb_ey)s",
                f"(UPPER(CAST({meas_col} AS STRING)) LIKE '%MID-MONTH%' OR UPPER(CAST({meas_col} AS STRING)) LIKE '%MID MONTH%' OR UPPER(CAST({meas_col} AS STRING)) LIKE '%MIDDLE OF MONTH%')",
                f"UPPER(TRIM(CAST({sub_col} AS STRING))) NOT LIKE 'TOTAL%'",
                f"UPPER(TRIM(CAST({sub_col} AS STRING))) NOT LIKE 'ALL %'",
            ]
            if stb_mark:
                params["stb_mark"] = stb_mark
                where_clauses.append(f"UPPER(TRIM(CAST({aar_col} AS STRING))) = %(stb_mark)s")
            if sub_measure_prefix:
                params["stb_sub"] = f"%{sub_measure_prefix.strip().upper()}%"
                where_clauses.append(
                    f"(UPPER(TRIM(CAST({sub_col} AS STRING))) LIKE %(stb_sub)s OR UPPER(TRIM(CAST({line_col} AS STRING))) LIKE %(stb_sub)s)"
                )

            where_sql = " AND ".join(where_clauses)
            fq_stb = config.fq_table(config.stb_1246_table)

            q_carrier = f"""
            WITH monthly AS (
                SELECT UPPER(TRIM(CAST({aar_col} AS STRING))) AS stb_aar_mark, {yr_expr} AS y, {mo_expr} AS m, SUM({num_val}) AS emp
                FROM {fq_stb} e WHERE {where_sql} GROUP BY 1, 2, 3
            )
            SELECT stb_aar_mark, COUNT(*) AS months_reported, ROUND(AVG(emp), 1) AS avg_monthly_employees,
                   ROUND(MIN(emp), 0) AS min_monthly_employees, ROUND(MAX(emp), 0) AS max_monthly_employees
            FROM monthly GROUP BY stb_aar_mark ORDER BY avg_monthly_employees DESC
            """
            q_craft = f"""
            WITH monthly AS (
                SELECT TRIM(CAST({sub_col} AS STRING)) AS craft_category, {yr_expr} AS y, {mo_expr} AS m, SUM({num_val}) AS emp
                FROM {fq_stb} e WHERE {where_sql} GROUP BY 1, 2, 3
            )
            SELECT craft_category, ROUND(AVG(emp), 1) AS avg_monthly_employees
            FROM monthly GROUP BY craft_category ORDER BY craft_category ASC
            """
            carrier_rows = execute_query(q_carrier, params)
            craft_rows = execute_query(q_craft, params)
            total_emp = round(sum(float(r["avg_monthly_employees"] or 0) for r in carrier_rows), 1)

            rates: Dict[str, Any] = {
                "fra_parent_railroad_matched": fra_parent,
                "train_accidents_form54": None,
                "employee_on_duty_casualties_form55a": None,
                "train_accidents_per_1000_employees": None,
                "employee_casualties_per_1000_employees": None,
            }
            if not state and total_emp > 0:
                p_fra: Dict[str, Any] = {}
                cls_flt = None if fra_parent else "1"
                c54 = get_table_columns(config.form_54_table)
                inc_col = resolve_col(c54, "f", ("incident_key", "accident_number"))
                jcd_col = resolve_col(c54, "f", ("joint_cd",))
                t54 = build_time_predicate(c54, "f", "st54", p_fra, ("year", "accident_year"), ("accident_month",), ("date",), start_year, end_year, "calendar")
                f54_c = build_common_filters(c54, "f", "sc54", p_fra, False, None, None, None, None, None, None, fra_parent, cls_flt, None)
                f54_x = build_form54_filters(c54, "f", "sx54", p_fra, include_crossings=False)
                acc_cnt = int(execute_query(f"SELECT COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' THEN {inc_col} END) AS cnt FROM {config.fq_table(config.form_54_table)} f WHERE {t54} {f54_c} {f54_x}", p_fra)[0]["cnt"] or 0)

                c55a = get_table_columns(config.form_55a_table)
                pt_col = resolve_col(c55a, "a", ("type_of_person", "type_of_person_code"))
                t55a = build_time_predicate(c55a, "a", "st55a", p_fra, ("incident_year", "year"), ("incident_month",), ("date",), start_year, end_year, "calendar")
                f55a_c = build_common_filters(c55a, "a", "sc55a", p_fra, False, None, None, None, None, None, None, fra_parent, cls_flt, None)
                cas_cnt = int(execute_query(f"SELECT COUNT(*) AS cnt FROM {config.fq_table(config.form_55a_table)} a WHERE {t55a} {f55a_c} AND (UPPER(CAST({pt_col} AS STRING)) LIKE '%EMPLOYEE ON DUTY%' OR TRIM(CAST({pt_col} AS STRING)) = 'A')", p_fra)[0]["cnt"] or 0)

                rates.update({
                    "train_accidents_form54": acc_cnt,
                    "employee_on_duty_casualties_form55a": cas_cnt,
                    "train_accidents_per_1000_employees": round((acc_cnt / total_emp) * 1000, 2),
                    "employee_casualties_per_1000_employees": round((cas_cnt / total_emp) * 1000, 2),
                })

            note = (
                "STB GTC (Grand Trunk Corp.) reflects CN's U.S. Class I subsidiary operations only; FRA parent_railroad_code='CN' aggregates CN's U.S. operating subsidiaries."
                if stb_mark == "GTC"
                else "STB Part 1246 covers U.S. Class I railroad operations at the system level (no state breakdown)."
            )
            return {
                "dataset": f"STB 49 CFR Part 1246 Monthly Employment ({config.stb_1246_table})",
                "filters_applied": {"start_year": start_year, "end_year": end_year, "requested_railroad_code": railroad_code, "resolved_stb_aar_mark": stb_mark, "resolved_fra_parent_code": fra_parent, "sub_measure_prefix": sub_measure_prefix, "state": state},
                "total_avg_monthly_employees": total_emp,
                "carrier_employment_summary": carrier_rows,
                "craft_breakdown_l100_to_l600": craft_rows,
                "cross_form_fra_safety_rates": rates,
                "regulatory_scope_note": note,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}
