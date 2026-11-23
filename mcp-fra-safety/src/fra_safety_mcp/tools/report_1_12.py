from typing import Any, Dict, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_form54_filters, build_time_predicate


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_report_1_12_rail_safety_overview(
        start_year: int = 2016,
        end_year: int = 2025,
        year_type: str = "calendar",
        railroad_code: Optional[str] = None,
        parent_railroad_code: Optional[str] = None,
        railroad_class: Optional[str] = None,
        railroad_group: Optional[str] = None,
        fra_region: Optional[str] = None,
        smt: Optional[str] = None,
        state: Optional[str] = None,
        county: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        has_geo_filter = bool(state or county or city)
        params: Dict[str, Any] = {}

        try:
            c54 = get_table_columns(config.form_54_table)
            inc_col = resolve_col(c54, "f", ("incident_key", "accident_number"))
            jcd_col = resolve_col(c54, "f", ("joint_cd", "joint_code"))
            typ_code_col = resolve_col(c54, "f", ("accident_type_code", "typacc", "accident_type"), fallback_sql="'0'")
            typ_text_col = resolve_col(c54, "f", ("accident_type", "accident_type_code", "typacc"), fallback_sql="''")
            cau_col = resolve_col(c54, "f", ("primary_accident_cause_code", "accident_cause_code", "cause"), fallback_sql="''")
            trk_code_col = resolve_col(c54, "f", ("track_type_code", "typtrk", "track_type"), fallback_sql="''")
            trk_text_col = resolve_col(c54, "f", ("track_type", "track_type_code", "typtrk"), fallback_sql="''")
            dmg_col = resolve_col(c54, "f", ("total_damage_cost", "equipment_damage_cost"), fallback_sql="0")
            haz_col = resolve_col(c54, "f", ("hazmat_cars_damaged", "hazmat_cars_damaged_derailed", "carsdmg"), fallback_sql="0")

            t54 = build_time_predicate(
                c54, "f", "t54", params,
                ("year", "accident_year", "year4", "iyr"), ("accident_month", "imo", "month"), ("date",),
                start_year, end_year, year_type,
            )
            f54_common = build_common_filters(
                c54, "f", "c54", params, True, state, county, city, fra_region, smt,
                railroad_code, parent_railroad_code, railroad_class, railroad_group,
            )
            f54_excl = build_form54_filters(c54, "f", "x54", params, include_crossings=False)

            q54 = f"""
            SELECT
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' THEN {inc_col} END) AS train_accidents,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1'
                    AND (TRIM(CAST({typ_code_col} AS STRING)) = '1' OR UPPER(CAST({typ_text_col} AS STRING)) LIKE '%DERAIL%')
                    THEN {inc_col} END) AS derailments,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1'
                    AND (TRIM(CAST({typ_code_col} AS STRING)) IN ('2','3','4','5','6') OR UPPER(CAST({typ_text_col} AS STRING)) LIKE '%COLLISION%')
                    THEN {inc_col} END) AS collisions,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' AND UPPER(TRIM(CAST({cau_col} AS STRING))) LIKE 'H%' THEN {inc_col} END) AS cause_human_factor,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' AND UPPER(TRIM(CAST({cau_col} AS STRING))) LIKE 'T%' THEN {inc_col} END) AS cause_track,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' AND UPPER(TRIM(CAST({cau_col} AS STRING))) LIKE 'E%' THEN {inc_col} END) AS cause_mechanical,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' AND UPPER(TRIM(CAST({cau_col} AS STRING))) LIKE 'S%' THEN {inc_col} END) AS cause_signal,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' AND UPPER(TRIM(CAST({cau_col} AS STRING))) LIKE 'M%' THEN {inc_col} END) AS cause_misc,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1'
                    AND (TRIM(CAST({trk_code_col} AS STRING)) = '1' OR UPPER(CAST({trk_text_col} AS STRING)) LIKE '%MAIN%')
                    THEN {inc_col} END) AS track_main_line,
                COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1'
                    AND (TRIM(CAST({trk_code_col} AS STRING)) = '2' OR UPPER(CAST({trk_text_col} AS STRING)) LIKE '%YARD%')
                    THEN {inc_col} END) AS track_yard,
                COALESCE(SUM(CAST({dmg_col} AS DOUBLE)), 0) AS total_damage_cost,
                COALESCE(SUM(CAST({haz_col} AS INT)), 0) AS hazmat_cars_damaged_derailed
            FROM {config.fq_table(config.form_54_table)} f
            WHERE {t54} {f54_common} {f54_excl}
            """

            c57 = get_table_columns(config.form_57_table)
            pub_col = resolve_col(c57, "c", ("public_private", "public_private_code"), fallback_sql="''")
            k57_col = resolve_col(c57, "c", ("total_killed_form57", "crossing_users_killed", "total_killed"), fallback_sql="0")
            i57_col = resolve_col(c57, "c", ("total_injured_form57", "crossing_users_injured", "total_injured"), fallback_sql="0")

            t57 = build_time_predicate(
                c57, "c", "t57", params,
                ("year", "incident_year", "iyr"), ("incident_month", "month", "imo"), ("date",),
                start_year, end_year, year_type,
            )
            f57_common = build_common_filters(
                c57, "c", "c57", params, True, state, county, city, fra_region, smt,
                railroad_code, parent_railroad_code, railroad_class, railroad_group,
            )
            q57 = f"""
            SELECT
                COUNT(*) AS crossing_incidents,
                SUM(CASE WHEN UPPER(CAST({pub_col} AS STRING)) LIKE '%PUBLIC%' OR TRIM(CAST({pub_col} AS STRING)) = '3' THEN 1 ELSE 0 END) AS public_crossing_incidents,
                COALESCE(SUM(CAST({k57_col} AS INT)), 0) AS crossing_fatalities,
                COALESCE(SUM(CAST({i57_col} AS INT)), 0) AS crossing_injuries
            FROM {config.fq_table(config.form_57_table)} c
            WHERE {t57} {f57_common}
            """

            c55a = get_table_columns(config.form_55a_table)
            pt_col = resolve_col(c55a, "a", ("type_of_person", "type_of_person_code", "person_type"), fallback_sql="''")
            fat_col = resolve_col(c55a, "a", ("fatality", "ifatal", "fatal"), fallback_sql="''")

            t55a = build_time_predicate(
                c55a, "a", "t55a", params,
                ("incident_year", "year", "iyr"), ("incident_month", "month", "imo"), ("date",),
                start_year, end_year, year_type,
            )
            f55a_common = build_common_filters(
                c55a, "a", "c55a", params, True, state, county, city, fra_region, smt,
                railroad_code, parent_railroad_code, railroad_class, railroad_group,
            )
            q55a = f"""
            SELECT
                COUNT(*) AS form55a_total_casualties,
                SUM(CASE WHEN UPPER(TRIM(CAST({fat_col} AS STRING))) IN ('Y', 'YES', '1', 'TRUE') THEN 1 ELSE 0 END) AS form55a_fatalities,
                SUM(CASE WHEN UPPER(CAST({pt_col} AS STRING)) LIKE '%EMPLOYEE ON DUTY%' OR TRIM(CAST({pt_col} AS STRING)) = 'A' THEN 1 ELSE 0 END) AS employee_on_duty_casualties,
                SUM(CASE WHEN (UPPER(CAST({pt_col} AS STRING)) LIKE '%TRESPASSER%' OR TRIM(CAST({pt_col} AS STRING)) = 'E')
                    AND UPPER(TRIM(CAST({fat_col} AS STRING))) IN ('Y', 'YES', '1', 'TRUE') THEN 1 ELSE 0 END) AS trespasser_fatalities,
                SUM(CASE WHEN (UPPER(CAST({pt_col} AS STRING)) LIKE '%TRESPASSER%' OR TRIM(CAST({pt_col} AS STRING)) = 'E')
                    AND UPPER(TRIM(CAST({fat_col} AS STRING))) NOT IN ('Y', 'YES', '1', 'TRUE') THEN 1 ELSE 0 END) AS trespasser_injuries
            FROM {config.fq_table(config.form_55a_table)} a
            WHERE {t55a} {f55a_common}
            """

            res54 = execute_query(q54, params)[0]
            res57 = execute_query(q57, params)[0]
            res55a = execute_query(q55a, params)[0]

            operational: Dict[str, Any] = {
                "number_of_railroads_included": None,
                "total_train_miles": None,
                "main_line_miles": None,
                "yard_switching_miles": None,
                "employee_hours_worked": None,
                "passengers_transported": None,
                "rate_total_acc_inc_per_million_train_miles": None,
                "rate_train_accidents_per_million_train_miles": None,
                "rate_highway_rail_incidents_per_million_train_miles": None,
                "rate_employees_on_duty_per_200k_hours": None,
            }
            op_note = (
                "Operational exposure (Form 55) and normalized rates are intentionally None/blank "
                "because a State, County, or City filter is active (matching official FRA Report 1.12 portal rules)."
                if has_geo_filter
                else "Normalized rates computed from Form 55 operational exposure denominators in Unity Catalog."
            )

            if not has_geo_filter:
                c55 = get_table_columns(config.form_55_table)
                rr55_col = resolve_col(
                    c55, "o", ("railroad_code", "reporting_railroad_code"), fallback_sql="NULL"
                )
                tm_col = resolve_col(c55, "o", ("total_miles", "total_train_miles"), fallback_sql="0")
                fr_col = resolve_col(c55, "o", ("freight_train_miles",), fallback_sql="0")
                ps_col = resolve_col(c55, "o", ("passenger_train_miles",), fallback_sql="0")
                yd_col = resolve_col(c55, "o", ("yard_switching_miles",), fallback_sql="0")
                ot_col = resolve_col(c55, "o", ("other_train_miles",), fallback_sql="0")
                hr_col = resolve_col(c55, "o", ("employee_man_hours", "employee_hours_worked"), fallback_sql="0")
                px_col = resolve_col(c55, "o", ("passengers_transported",), fallback_sql="0")

                comp_sum = (
                    f"(COALESCE(CAST({fr_col} AS DOUBLE), 0) + COALESCE(CAST({ps_col} AS DOUBLE), 0) "
                    f"+ COALESCE(CAST({yd_col} AS DOUBLE), 0) + COALESCE(CAST({ot_col} AS DOUBLE), 0))"
                )

                t55 = build_time_predicate(
                    c55, "o", "t55", params,
                    ("year", "year4", "iyr"), ("report_month", "month", "imo"), ("date",),
                    start_year, end_year, year_type,
                )
                f55_common = build_common_filters(
                    c55, "o", "c55", params, False, None, None, None, fra_region, smt,
                    railroad_code, parent_railroad_code, railroad_class, railroad_group,
                )
                q55 = f"""
                SELECT
                    COUNT(DISTINCT {rr55_col}) AS number_of_railroads_included,
                    COALESCE(SUM(COALESCE(NULLIF(CAST({tm_col} AS DOUBLE), 0), {comp_sum})), 0) AS total_train_miles,
                    COALESCE(SUM(CAST({fr_col} AS DOUBLE) + CAST({ps_col} AS DOUBLE)), 0) AS main_line_miles,
                    COALESCE(SUM(CAST({yd_col} AS DOUBLE)), 0) AS yard_switching_miles,
                    COALESCE(SUM(CAST({hr_col} AS DOUBLE)), 0) AS employee_hours_worked,
                    COALESCE(SUM(CAST({px_col} AS DOUBLE)), 0) AS passengers_transported
                FROM {config.fq_table(config.form_55_table)} o
                WHERE {t55} {f55_common}
                """
                res55 = execute_query(q55, params)[0]
                tm = float(res55["total_train_miles"] or 0.0)
                hrs = float(res55["employee_hours_worked"] or 0.0)
                train_acc = int(res54["train_accidents"] or 0)
                xing_inc = int(res57["crossing_incidents"] or 0)
                total_events = train_acc + xing_inc + int(res55a["form55a_total_casualties"] or 0)
                emp_cas = int(res55a["employee_on_duty_casualties"] or 0)

                operational.update({
                    "number_of_railroads_included": int(res55["number_of_railroads_included"] or 0),
                    "total_train_miles": round(tm, 2),
                    "main_line_miles": round(float(res55["main_line_miles"] or 0.0), 2),
                    "yard_switching_miles": round(float(res55["yard_switching_miles"] or 0.0), 2),
                    "employee_hours_worked": round(hrs, 2),
                    "passengers_transported": int(res55["passengers_transported"] or 0),
                    "rate_total_acc_inc_per_million_train_miles": round((total_events / tm) * 1_000_000, 3) if tm > 0 else None,
                    "rate_train_accidents_per_million_train_miles": round((train_acc / tm) * 1_000_000, 3) if tm > 0 else None,
                    "rate_highway_rail_incidents_per_million_train_miles": round((xing_inc / tm) * 1_000_000, 3) if tm > 0 else None,
                    "rate_employees_on_duty_per_200k_hours": round((emp_cas / hrs) * 200_000, 3) if hrs > 0 else None,
                })

            xing_total = int(res57["crossing_incidents"] or 0)
            public_pct = round((int(res57["public_crossing_incidents"] or 0) / xing_total) * 100, 2) if xing_total > 0 else None

            return {
                "report": "FRA Report 1.12 - Rail Safety Overview",
                "portal_reference": "https://data.transportation.gov/stories/s/dsuf-xcni",
                "data_source": f"Databricks Unity Catalog ({config.catalog}.{config.schema})",
                "filters_applied": {
                    "start_year": start_year,
                    "end_year": end_year,
                    "year_type": year_type,
                    "railroad_code": railroad_code,
                    "parent_railroad_code": parent_railroad_code,
                    "railroad_class": railroad_class,
                    "railroad_group": railroad_group,
                    "fra_region": fra_region,
                    "smt": smt,
                    "state": state,
                    "county": county,
                    "city": city,
                },
                "train_accidents_form54": res54,
                "highway_rail_crossings_form57": {**res57, "public_crossing_pct": public_pct},
                "casualties_form55a": res55a,
                "operational_and_rates_form55": operational,
                "operational_exposure_note": op_note,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}
