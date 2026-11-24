from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_form54_filters, build_time_predicate


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def analyze_metro_corridor_safety(
        cities: List[str],
        state: Optional[str] = None,
        start_year: int = 2016,
        end_year: int = 2025,
        year_type: str = "calendar",
        railroad_code: Optional[str] = None,
        parent_railroad_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not cities:
            return {
                "error": "At least one city name must be provided in `cities`.",
                "hint": "Example: cities=['Chicago'] or cities=['Newark', 'Jersey City']",
            }

        has_carrier_filter = bool(railroad_code or parent_railroad_code)

        try:
            c54 = get_table_columns(config.form_54_table)
            c57 = get_table_columns(config.form_57_table)
            c55a = get_table_columns(config.form_55a_table)

            inc_col = resolve_col(c54, "f", ("incident_key", "accident_number"))
            jcd_col = resolve_col(c54, "f", ("joint_cd", "joint_code"))
            dmg_col = resolve_col(c54, "f", ("total_damage_cost", "equipment_damage_cost"), fallback_sql="0")

            count_expr = (
                f"COUNT(DISTINCT {inc_col})"
                if has_carrier_filter
                else f"COUNT(DISTINCT CASE WHEN TRIM(CAST({jcd_col} AS STRING)) = '1' THEN {inc_col} END)"
            )

            k57_col = resolve_col(c57, "c", ("total_killed_form57", "crossing_users_killed", "total_killed"), fallback_sql="0")
            i57_col = resolve_col(c57, "c", ("total_injured_form57", "crossing_users_injured", "total_injured"), fallback_sql="0")

            pt_col = resolve_col(c55a, "a", ("type_of_person", "type_of_person_code", "person_type"), fallback_sql="''")
            fat_col = resolve_col(c55a, "a", ("fatality", "ifatal", "fatal"), fallback_sql="''")

            city_breakdowns: List[Dict[str, Any]] = []
            tot_accidents = 0
            tot_damage = 0.0
            tot_crossings = 0
            tot_crossing_fatalities = 0

            for idx, city_name in enumerate(cities):
                pfx = f"m{idx}"
                params: Dict[str, Any] = {}

                t54 = build_time_predicate(
                    c54, "f", f"{pfx}_t54", params,
                    ("year", "accident_year", "year4", "iyr"), ("accident_month", "imo", "month"), ("date",),
                    start_year, end_year, year_type,
                )
                f54_common = build_common_filters(
                    c54, "f", f"{pfx}_c54", params, True, state, None, city_name,
                    None, None, railroad_code, parent_railroad_code, None, None,
                )
                f54_excl = build_form54_filters(c54, "f", f"{pfx}_x54", params, include_crossings=False)

                q54 = f"""
                SELECT
                    {count_expr} AS train_accidents,
                    COALESCE(SUM(CAST({dmg_col} AS DOUBLE)), 0) AS total_damage_cost
                FROM {config.fq_table(config.form_54_table)} f
                WHERE {t54} {f54_common} {f54_excl}
                """

                t57 = build_time_predicate(
                    c57, "c", f"{pfx}_t57", params,
                    ("year", "incident_year", "iyr"), ("incident_month", "month", "imo"), ("date",),
                    start_year, end_year, year_type,
                )
                f57_common = build_common_filters(
                    c57, "c", f"{pfx}_c57", params, True, state, None, city_name,
                    None, None, railroad_code, parent_railroad_code, None, None,
                )
                q57 = f"""
                SELECT
                    COUNT(*) AS crossing_incidents,
                    COALESCE(SUM(CAST({k57_col} AS INT)), 0) AS crossing_fatalities,
                    COALESCE(SUM(CAST({i57_col} AS INT)), 0) AS crossing_injuries
                FROM {config.fq_table(config.form_57_table)} c
                WHERE {t57} {f57_common}
                """

                r54 = execute_query(q54, params)[0]
                r57 = execute_query(q57, params)[0]

                acc = int(r54["train_accidents"] or 0)
                dmg = float(r54["total_damage_cost"] or 0.0)
                xing = int(r57["crossing_incidents"] or 0)
                xing_fat = int(r57["crossing_fatalities"] or 0)

                tot_accidents += acc
                tot_damage += dmg
                tot_crossings += xing
                tot_crossing_fatalities += xing_fat

                city_breakdowns.append({
                    "city": city_name,
                    "state": state,
                    "train_accidents_form54": acc,
                    "total_damage_cost_form54": round(dmg, 2),
                    "crossing_incidents_form57": xing,
                    "crossing_fatalities_form57": xing_fat,
                })

            params_55a: Dict[str, Any] = {}
            t55a = build_time_predicate(
                c55a, "a", "m_t55a", params_55a,
                ("incident_year", "year", "iyr"), ("incident_month", "month", "imo"), ("date",),
                start_year, end_year, year_type,
            )
            f55a_common = build_common_filters(
                c55a, "a", "m_c55a", params_55a, True, state, None, None,
                None, None, railroad_code, parent_railroad_code, None, None,
            )
            q55a = f"""
            SELECT
                COUNT(*) AS total_casualties,
                SUM(CASE WHEN UPPER(TRIM(CAST({fat_col} AS STRING))) IN ('Y', 'YES', '1', 'TRUE') THEN 1 ELSE 0 END) AS total_fatalities,
                SUM(CASE WHEN (UPPER(CAST({pt_col} AS STRING)) LIKE '%TRESPASSER%' OR TRIM(CAST({pt_col} AS STRING)) = 'E')
                    AND UPPER(TRIM(CAST({fat_col} AS STRING))) IN ('Y', 'YES', '1', 'TRUE') THEN 1 ELSE 0 END) AS trespasser_fatalities
            FROM {config.fq_table(config.form_55a_table)} a
            WHERE {t55a} {f55a_common}
            """
            r55a = execute_query(q55a, params_55a)[0]

            return {
                "report": "FRA Multi-Portal Metro Corridor Safety Synthesis",
                "filters_applied": {
                    "cities": cities,
                    "state": state,
                    "start_year": start_year,
                    "end_year": end_year,
                    "year_type": year_type,
                    "railroad_code": railroad_code,
                    "parent_railroad_code": parent_railroad_code,
                },
                "corridor_summary": {
                    "total_train_accidents_form54": tot_accidents,
                    "total_damage_cost_form54": round(tot_damage, 2),
                    "total_crossing_incidents_form57": tot_crossings,
                    "total_crossing_fatalities_form57": tot_crossing_fatalities,
                    "statewide_casualties_form55a": int(r55a["total_casualties"] or 0),
                    "statewide_trespasser_fatalities_form55a": int(r55a["trespasser_fatalities"] or 0),
                },
                "city_breakdown": city_breakdowns,
                "form55a_geography_note": "Form 55a casualties are reported at the state/county level (no city field in FRA Form 55a).",
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}