from typing import Any, Dict, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_form57_filters, build_time_predicate, resolve_year_expr


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def analyze_highway_rail_crossings(
        start_year: int = 2016,
        end_year: int = 2025,
        year_type: str = "calendar",
        report_view: str = "warning_device_2_08",
        railroad_code: Optional[str] = None,
        parent_railroad_code: Optional[str] = None,
        railroad_class: Optional[str] = None,
        railroad_group: Optional[str] = None,
        fra_region: Optional[str] = None,
        smt: Optional[str] = None,
        state: Optional[str] = None,
        county: Optional[str] = None,
        city: Optional[str] = None,
        crossing_type: Optional[str] = None,
        highway_user: Optional[str] = None,
        warning_device: Optional[str] = None,
        struck_by: Optional[str] = None,
        crossing_id: Optional[str] = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        safe_limit = max(1, min(int(limit), 200))

        try:
            c57 = get_table_columns(config.form_57_table)
            k_col = resolve_col(c57, "c", ("total_killed_form57", "crossing_users_killed", "total_killed"), fallback_sql="0")
            i_col = resolve_col(c57, "c", ("total_injured_form57", "crossing_users_injured", "total_injured"), fallback_sql="0")
            pub_col = resolve_col(c57, "c", ("public_private", "public_private_code"), fallback_sql="'Unknown'")

            t57 = build_time_predicate(
                c57, "c", "t57", params,
                ("year", "incident_year", "iyr"), ("incident_month", "month", "imo"), ("date",),
                start_year, end_year, year_type,
            )
            f57_common = build_common_filters(
                c57, "c", "c57", params, True, state, county, city, fra_region, smt,
                railroad_code, parent_railroad_code, railroad_class, railroad_group,
            )
            f57_spec = build_form57_filters(
                c57, "c", "s57", params,
                crossing_type=crossing_type,
                highway_user=highway_user,
                warning_device=warning_device,
                struck_by=struck_by,
                crossing_id=crossing_id,
            )

            view = report_view.strip().lower()
            if view in ("warning_device_2_08", "warning_device"):
                dim_col = resolve_col(
                    c57,
                    "c",
                    ("crossing_warning", "crossing_warning_code", "warning_device", "wdcode"),
                )
                dim_label = "warning_device"
                report_name = "FRA Report 2.08 - Grade Crossing Incidents by Warning Device"
                extra_cols = ""
            elif view in ("highway_user_5_14", "highway_user"):
                dim_col = resolve_col(
                    c57,
                    "c",
                    ("highway_user", "highway_user_code", "typveh"),
                )
                dim_label = "highway_user"
                report_name = "FRA Report 5.14 - Grade Crossing Incidents by Highway User"
                extra_cols = ""
            elif view in ("struck_by_5_15", "struck_by"):
                dim_col = resolve_col(
                    c57,
                    "c",
                    ("equipment_struck", "equipment_struck_code", "struck_by", "typacci"),
                )
                dim_label = "struck_by"
                report_name = "FRA Report 5.15 - Grade Crossing Incidents by Struck-By Direction"
                extra_cols = ""
            elif view in ("crossing_hotspots", "hotspots", "crossing_id"):
                dim_col = resolve_col(
                    c57,
                    "c",
                    ("grade_crossing_id", "crossing_id", "gxid", "usdot_crossing_id"),
                )
                dim_label = "usdot_crossing_id"
                report_name = "FRA Form 57 - Repeat-Incident USDOT Crossing Hotspots"
                st_c = resolve_col(c57, "c", ("state_name", "state_code", "state_abbr"), fallback_sql="''")
                ct_c = resolve_col(c57, "c", ("city_name", "nearest_station"), fallback_sql="''")
                rr_c = resolve_col(c57, "c", ("railroad_code", "reporting_railroad_code"), fallback_sql="''")
                wd_c = resolve_col(
                    c57,
                    "c",
                    ("crossing_warning", "crossing_warning_code"),
                    fallback_sql="''",
                )
                extra_cols = (
                    f", MAX(CAST({st_c} AS STRING)) AS state"
                    f", MAX(CAST({ct_c} AS STRING)) AS city"
                    f", MAX(CAST({rr_c} AS STRING)) AS railroad_code"
                    f", MAX(CAST({wd_c} AS STRING)) AS warning_device"
                )
            elif view in ("year", "yearly"):
                dim_col = resolve_year_expr(c57, "c", ("year", "incident_year", "iyr"), ("date",))
                dim_label = "year"
                report_name = "FRA Form 57 - Grade Crossing Incidents by Year"
                extra_cols = ""
            else:
                dim_col = resolve_col(c57, "c", ("state_name", "state_code", "state_abbr"), fallback_sql="'ALL'")
                dim_label = "state"
                report_name = "FRA Report 1.11 - Highway-Rail Grade Crossing Overview"
                extra_cols = ""

            q_totals = f"""
            SELECT
                COUNT(*) AS total_incidents,
                SUM(CASE WHEN UPPER(CAST({pub_col} AS STRING)) LIKE '%PUBLIC%' OR TRIM(CAST({pub_col} AS STRING)) = '3' THEN 1 ELSE 0 END) AS public_incidents,
                COALESCE(SUM(CAST({k_col} AS INT)), 0) AS total_fatalities,
                COALESCE(SUM(CAST({i_col} AS INT)), 0) AS total_injuries
            FROM {config.fq_table(config.form_57_table)} c
            WHERE {t57} {f57_common} {f57_spec}
            """

            q_breakdown = f"""
            SELECT
                COALESCE(NULLIF(TRIM(CAST({dim_col} AS STRING)), ''), 'UNSPECIFIED') AS {dim_label},
                COUNT(*) AS incident_count,
                COALESCE(SUM(CAST({k_col} AS INT)), 0) AS fatalities,
                COALESCE(SUM(CAST({i_col} AS INT)), 0) AS injuries
                {extra_cols}
            FROM {config.fq_table(config.form_57_table)} c
            WHERE {t57} {f57_common} {f57_spec}
            GROUP BY 1
            ORDER BY incident_count DESC, fatalities DESC
            LIMIT {safe_limit}
            """

            totals = execute_query(q_totals, params)[0]
            breakdown = execute_query(q_breakdown, params)

            return {
                "report": report_name,
                "portal_reference": "https://data.transportation.gov/stories/s/9hnw-nt86",
                "report_view": report_view,
                "totals": totals,
                "breakdown": breakdown,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}
