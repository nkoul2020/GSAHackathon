import re
from typing import Any, Dict, List, Optional, Set
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query, get_table_columns, resolve_col
from ..queries import build_common_filters, build_time_predicate, resolve_year_expr

_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|REPLACE|GRANT|REVOKE|COPY|PUT|REMOVE|VACUUM|OPTIMIZE|CALL|EXEC)\b",
    re.IGNORECASE,
)


def _qualify_fra_tables(sql: str) -> str:
    """Rewrites unqualified FRA table references to `users.neeraj_koul.<table>`."""
    tables = (
        config.form_54_table,
        config.form_55a_table,
        config.form_55_table,
        config.form_57_table,
        config.stb_1246_table,
    )
    qualified = sql
    for tbl in tables:
        fq = config.fq_table(tbl)
        pattern = re.compile(rf"(?<![\w.`])`?{re.escape(tbl)}`?(?![\w`])", re.IGNORECASE)
        qualified = pattern.sub(fq, qualified)
    return qualified


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def walk_across_fra_forms(
        incident_key: Optional[str] = None,
        incident_number: Optional[str] = None,
        crossing_id: Optional[str] = None,
        state: Optional[str] = None,
        railroad_code: Optional[str] = None,
        parent_railroad_code: Optional[str] = None,
        start_year: int = 2020,
        end_year: int = 2025,
        year_type: str = "calendar",
        only_multi_form: bool = True,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Walks linked incidents across FRA Form 54 (Train Accidents), Form 57 (Grade Crossings),
        and Form 55a (Individual Casualties) in Unity Catalog (`users.neeraj_koul`).

        Supports targeted lookup by `incident_key`, carrier `incident_number` / `accidentnumber`,
        or USDOT `crossing_id` (`gxid` / `gradecrossingid`), as well as multi-form discovery
        filtered by `state`, `railroad_code`, `parent_railroad_code`, and year range.
        """
        safe_limit = max(1, min(int(limit), 50))
        fq54 = config.fq_table(config.form_54_table)
        fq55a = config.fq_table(config.form_55a_table)
        fq57 = config.fq_table(config.form_57_table)

        try:
            c54 = get_table_columns(config.form_54_table)
            c55a = get_table_columns(config.form_55a_table)
            c57 = get_table_columns(config.form_57_table)

            # Form 54 columns
            inc54 = resolve_col(c54, "f", ("incident_key",))
            accnum54 = resolve_col(c54, "f", ("accident_number",))
            rr54 = resolve_col(c54, "f", ("reporting_railroad_code", "railroad_code"))
            yr54 = resolve_year_expr(c54, "f", ("year", "accident_year"), ("date",))
            dt54 = resolve_col(c54, "f", ("date",), fallback_sql="''")
            jcd54 = resolve_col(c54, "f", ("joint_cd",))
            gxid54 = resolve_col(c54, "f", ("gxid",), fallback_sql="''")
            st54 = resolve_col(c54, "f", ("state_abbr", "state_name", "state_code"), fallback_sql="''")
            city54 = resolve_col(c54, "f", ("station",), fallback_sql="''")
            typ54 = resolve_col(c54, "f", ("accident_type", "accident_type_code"), fallback_sql="''")
            cau54_c = resolve_col(c54, "f", ("primary_accident_cause_code", "accident_cause_code"), fallback_sql="''")
            cau54_d = resolve_col(c54, "f", ("primary_accident_cause", "accident_cause"), fallback_sql="''")
            dmg54 = resolve_col(c54, "f", ("total_damage_cost",), fallback_sql="0")
            k54 = resolve_col(c54, "f", ("total_killed_form54", "total_persons_killed"), fallback_sql="0")
            i54 = resolve_col(c54, "f", ("total_injured_form54", "total_persons_injured"), fallback_sql="0")
            nar54 = resolve_col(c54, "f", ("narrative",), fallback_sql="''")

            # Form 55a columns
            inc55a = resolve_col(c55a, "a", ("incident_key",), fallback_sql="''")
            inum55a = resolve_col(c55a, "a", ("incident_number",))
            rr55a = resolve_col(c55a, "a", ("railroad_code",))
            yr55a = resolve_year_expr(c55a, "a", ("incident_year", "year"), ("date",))
            dt55a = resolve_col(c55a, "a", ("date",), fallback_sql="''")
            f54_flag_55a = resolve_col(c55a, "a", ("form54_filed",), fallback_sql="''")
            f57_flag_55a = resolve_col(c55a, "a", ("form57_filed",), fallback_sql="''")
            ptype55a = resolve_col(c55a, "a", ("type_of_person", "type_of_person_code"), fallback_sql="''")
            job55a = resolve_col(c55a, "a", ("employee_job_description",), fallback_sql="''")
            age55a = resolve_col(c55a, "a", ("age_of_person",), fallback_sql="NULL")
            inj55a = resolve_col(c55a, "a", ("injury_illness", "natinj"), fallback_sql="''")
            evt55a = resolve_col(c55a, "a", ("event",), fallback_sql="''")
            cau55a = resolve_col(c55a, "a", ("injury_cause",), fallback_sql="''")
            daw55a = resolve_col(c55a, "a", ("days_away_from_work",), fallback_sql="0")
            fat55a = resolve_col(c55a, "a", ("fatality", "ifatal"), fallback_sql="''")

            # Form 57 columns
            inum57 = resolve_col(c57, "c", ("incident_number",))
            rr57 = resolve_col(c57, "c", ("railroad_code",))
            yr57 = resolve_year_expr(c57, "c", ("year", "incident_year"), ("date",))
            dt57 = resolve_col(c57, "c", ("date",), fallback_sql="''")
            gxid57 = resolve_col(c57, "c", ("grade_crossing_id",), fallback_sql="''")
            f54_flag_57 = resolve_col(c57, "c", ("form54_filed",), fallback_sql="''")
            st57 = resolve_col(c57, "c", ("state_name", "state_code"), fallback_sql="''")
            city57 = resolve_col(c57, "c", ("city_name", "nearest_station"), fallback_sql="''")
            hwy57 = resolve_col(c57, "c", ("highway_name",), fallback_sql="''")
            pub57 = resolve_col(c57, "c", ("public_private",), fallback_sql="''")
            user57 = resolve_col(c57, "c", ("highway_user",), fallback_sql="''")
            warn57 = resolve_col(c57, "c", ("crossing_warning",), fallback_sql="''")
            struck57 = resolve_col(c57, "c", ("equipment_struck",), fallback_sql="''")
            k57 = resolve_col(c57, "c", ("total_killed_form57", "crossing_users_killed"), fallback_sql="0")
            i57 = resolve_col(c57, "c", ("total_injured_form57", "crossing_users_injured"), fallback_sql="0")

            params: Dict[str, Any] = {}
            f54_where: List[str] = []

            if incident_key:
                params["w_inc_key"] = incident_key.strip().upper()
                f54_where.append(f"UPPER(TRIM(CAST({inc54} AS STRING))) = %(w_inc_key)s")
            elif incident_number:
                params["w_inc_num"] = incident_number.strip().upper()
                f54_where.append(f"UPPER(TRIM(CAST({accnum54} AS STRING))) = %(w_inc_num)s")
            elif crossing_id:
                params["w_gxid"] = crossing_id.strip().upper()
                f54_where.append(f"UPPER(TRIM(CAST({gxid54} AS STRING))) = %(w_gxid)s")
            else:
                t54 = build_time_predicate(
                    c54, "f", "wt54", params,
                    ("year", "accident_year"), ("accident_month", "month"), ("date",),
                    start_year, end_year, year_type,
                )
                f54_where.append(t54)
                f54_where.append(f"TRIM(CAST({jcd54} AS STRING)) = '1'")
                if only_multi_form:
                    f54_where.append(
                        f"(COALESCE(CAST({k54} AS INT), 0) + COALESCE(CAST({i54} AS INT), 0) > 0 "
                        f"OR NULLIF(TRIM(CAST({gxid54} AS STRING)), '') IS NOT NULL)"
                    )

            common54 = build_common_filters(
                c54, "f", "wc54", params, True, state, None, None, None, None,
                railroad_code, parent_railroad_code, None, None,
            )

            q54 = f"""
            SELECT
                TRIM(CAST({inc54} AS STRING)) AS incident_key,
                TRIM(CAST({accnum54} AS STRING)) AS accident_number,
                UPPER(TRIM(CAST({rr54} AS STRING))) AS railroad_code,
                {yr54} AS year,
                CAST({dt54} AS STRING) AS date,
                UPPER(TRIM(CAST({st54} AS STRING))) AS state,
                TRIM(CAST({city54} AS STRING)) AS nearest_city_town,
                UPPER(TRIM(CAST({gxid54} AS STRING))) AS usdot_crossing_id,
                TRIM(CAST({jcd54} AS STRING)) AS joint_cd,
                CAST({typ54} AS STRING) AS accident_type,
                UPPER(TRIM(CAST({cau54_c} AS STRING))) AS primary_cause_code,
                CAST({cau54_d} AS STRING) AS primary_cause_desc,
                COALESCE(CAST({dmg54} AS DOUBLE), 0) AS total_damage_cost,
                COALESCE(CAST({k54} AS INT), 0) AS form54_killed,
                COALESCE(CAST({i54} AS INT), 0) AS form54_injured,
                CAST({nar54} AS STRING) AS narrative
            FROM {fq54} f
            WHERE {' AND '.join(f54_where)} {common54}
            ORDER BY total_damage_cost DESC
            LIMIT {safe_limit + 1}
            """
            form54_rows = execute_query(q54, params)
            f54_truncated = len(form54_rows) > safe_limit
            if f54_truncated:
                form54_rows = form54_rows[:safe_limit]

            inc_keys: Set[str] = {r["incident_key"] for r in form54_rows if r.get("incident_key")}
            gxids: Set[str] = {r["usdot_crossing_id"] for r in form54_rows if r.get("usdot_crossing_id")}
            if incident_key:
                inc_keys.add(incident_key.strip().upper())
            if crossing_id:
                gxids.add(crossing_id.strip().upper())

            # Walk Form 57 (Grade Crossings)
            form57_rows: List[Dict[str, Any]] = []
            f57_truncated = False
            if gxids or incident_number or (not form54_rows and (state or railroad_code or parent_railroad_code)):
                p57: Dict[str, Any] = {}
                w57: List[str] = []
                if gxids:
                    in_placeholders = []
                    for idx, g in enumerate(sorted(gxids)[:25]):
                        p57[f"gx_{idx}"] = g.upper()
                        in_placeholders.append(f"%(gx_{idx})s")
                    w57.append(f"UPPER(TRIM(CAST({gxid57} AS STRING))) IN ({', '.join(in_placeholders)})")
                    t57 = build_time_predicate(
                        c57, "c", "wt57", p57,
                        ("year", "incident_year"), ("incident_month", "month"), ("date",),
                        start_year, end_year, year_type,
                    )
                    w57.append(t57)
                elif incident_number:
                    p57["w57_inum"] = incident_number.strip().upper()
                    w57.append(f"UPPER(TRIM(CAST({inum57} AS STRING))) = %(w57_inum)s")
                else:
                    t57 = build_time_predicate(
                        c57, "c", "wt57", p57,
                        ("year", "incident_year"), ("incident_month", "month"), ("date",),
                        start_year, end_year, year_type,
                    )
                    w57.append(t57)
                    if only_multi_form:
                        w57.append(f"UPPER(TRIM(CAST({f54_flag_57} AS STRING))) IN ('Y', 'YES', '1', 'TRUE')")

                c57_flt = build_common_filters(
                    c57, "c", "wc57", p57, True, state, None, None, None, None,
                    railroad_code, parent_railroad_code, None, None,
                )
                q57 = f"""
                SELECT
                    TRIM(CAST({inum57} AS STRING)) AS incident_number,
                    UPPER(TRIM(CAST({rr57} AS STRING))) AS railroad_code,
                    {yr57} AS year,
                    CAST({dt57} AS STRING) AS date,
                    UPPER(TRIM(CAST({gxid57} AS STRING))) AS usdot_crossing_id,
                    TRIM(CAST({f54_flag_57} AS STRING)) AS form54_filed_flag,
                    TRIM(CAST({st57} AS STRING)) AS state,
                    TRIM(CAST({city57} AS STRING)) AS city,
                    TRIM(CAST({hwy57} AS STRING)) AS highway_name,
                    TRIM(CAST({pub57} AS STRING)) AS public_private,
                    TRIM(CAST({user57} AS STRING)) AS highway_user,
                    TRIM(CAST({warn57} AS STRING)) AS warning_device,
                    TRIM(CAST({struck57} AS STRING)) AS equipment_struck,
                    COALESCE(CAST({k57} AS INT), 0) AS form57_killed,
                    COALESCE(CAST({i57} AS INT), 0) AS form57_injured
                FROM {fq57} c
                WHERE {' AND '.join(w57)} {c57_flt}
                ORDER BY form57_killed DESC, form57_injured DESC
                LIMIT {safe_limit + 1}
                """
                form57_rows = execute_query(q57, p57)
                f57_truncated = len(form57_rows) > safe_limit
                if f57_truncated:
                    form57_rows = form57_rows[:safe_limit]

            # Walk Form 55a (Individual Casualties)
            form55a_rows: List[Dict[str, Any]] = []
            f55a_truncated = False
            if inc_keys or incident_number or form57_rows:
                p55a: Dict[str, Any] = {}
                or_links: List[str] = []

                if inc_keys:
                    ik_ph = []
                    for idx, ik in enumerate(sorted(inc_keys)[:30]):
                        p55a[f"ik_{idx}"] = ik.upper()
                        ik_ph.append(f"%(ik_{idx})s")
                    or_links.append(f"UPPER(TRIM(CAST({inc55a} AS STRING))) IN ({', '.join(ik_ph)})")

                if incident_number:
                    p55a["w55a_inum"] = incident_number.strip().upper()
                    or_links.append(f"UPPER(TRIM(CAST({inum55a} AS STRING))) = %(w55a_inum)s")

                for idx, xrow in enumerate(form57_rows[:15]):
                    if xrow.get("railroad_code") and xrow.get("incident_number") and xrow.get("year"):
                        p55a[f"xrr_{idx}"] = str(xrow["railroad_code"]).upper()
                        p55a[f"xin_{idx}"] = str(xrow["incident_number"]).upper()
                        p55a[f"xyr_{idx}"] = int(xrow["year"])
                        or_links.append(
                            f"(UPPER(TRIM(CAST({rr55a} AS STRING))) = %(xrr_{idx})s "
                            f"AND UPPER(TRIM(CAST({inum55a} AS STRING))) = %(xin_{idx})s "
                            f"AND {yr55a} = %(xyr_{idx})s)"
                        )

                if or_links:
                    q55a = f"""
                    SELECT
                        TRIM(CAST({inc55a} AS STRING)) AS incident_key,
                        TRIM(CAST({inum55a} AS STRING)) AS incident_number,
                        UPPER(TRIM(CAST({rr55a} AS STRING))) AS railroad_code,
                        {yr55a} AS year,
                        CAST({dt55a} AS STRING) AS date,
                        TRIM(CAST({f54_flag_55a} AS STRING)) AS form54_filed_flag,
                        TRIM(CAST({f57_flag_55a} AS STRING)) AS form57_filed_flag,
                        TRIM(CAST({ptype55a} AS STRING)) AS person_type,
                        TRIM(CAST({job55a} AS STRING)) AS employee_job,
                        CAST({age55a} AS INT) AS age,
                        TRIM(CAST({fat55a} AS STRING)) AS fatality_flag,
                        TRIM(CAST({inj55a} AS STRING)) AS injury_illness,
                        TRIM(CAST({evt55a} AS STRING)) AS event,
                        TRIM(CAST({cau55a} AS STRING)) AS injury_cause,
                        COALESCE(CAST({daw55a} AS INT), 0) AS days_away_from_work
                    FROM {fq55a} a
                    WHERE {' OR '.join(or_links)}
                    ORDER BY fatality_flag DESC, days_away_from_work DESC
                    LIMIT 101
                    """
                    form55a_rows = execute_query(q55a, p55a)
                    f55a_truncated = len(form55a_rows) > 100
                    if f55a_truncated:
                        form55a_rows = form55a_rows[:100]

            any_truncated = f54_truncated or f57_truncated or f55a_truncated
            return {
                "walk_summary": {
                    "form_54_train_accidents_matched": len(form54_rows),
                    "form_57_grade_crossings_matched": len(form57_rows),
                    "form_55a_casualty_records_matched": len(form55a_rows),
                    "limit_applied": safe_limit,
                    "truncated": {
                        "form_54": f54_truncated,
                        "form_57": f57_truncated,
                        "form_55a": f55a_truncated,
                    },
                    "truncation_note": (
                        f"More matching records exist beyond limit={safe_limit}. Increase `limit` (up to 50) "
                        "or narrow filters (incident_key, railroad_code, state, year) to inspect remaining records."
                        if any_truncated
                        else "All matching records across Forms 54, 57, and 55a were returned."
                    ),
                    "linkage_keys_used": [
                        "form_54_accidents.incidentkey = form_55a_casualties.incidentkey",
                        "form_54_accidents.gxid = form_57_crossings.gradecrossingid",
                        "(railroadcode, year, incidentnumber) across Forms 54, 57, and 55a",
                    ],
                },
                "form_54_train_accidents": form54_rows,
                "form_57_grade_crossings": form57_rows,
                "form_55a_individual_casualties": form55a_rows,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}

    @mcp.tool()
    def run_fra_sql_query(
        sql: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Executes a governed read-only SQL query (`SELECT` or `WITH`) in Databricks Unity Catalog
        across `form_54_accidents`, `form_55a_casualties`, `form_57_crossings`, and
        `form_55_operational` (`users.neeraj_koul`).

        Supports multi-table JOINs walking across Forms 54, 55a, 57, and 55. Write/DDL statements
        are blocked and output rows are capped at `limit` (max 1000).
        """
        raw_sql = (sql or "").strip().rstrip(";").strip()
        if not raw_sql:
            return {
                "error": "SQL query cannot be empty.",
                "hint": "Provide a SELECT or WITH query joining form_54_accidents, form_55a_casualties, or form_57_crossings.",
            }

        cleaned = re.sub(r"^\s*(--[^\n]*\n|/\*[\s\S]*?\*/\s*)*", "", raw_sql).strip()
        first_word = cleaned.split(None, 1)[0].upper() if cleaned else ""

        if first_word not in ("SELECT", "WITH"):
            return {
                "error": f"Only read-only SELECT or WITH queries are permitted (received '{first_word}').",
                "hint": "Rewrite your query starting with SELECT or WITH.",
            }

        forbidden_match = _FORBIDDEN_SQL_PATTERN.search(cleaned)
        if forbidden_match:
            return {
                "error": f"Blocked SQL keyword '{forbidden_match.group(1).upper()}' detected.",
                "hint": "Only read-only analytical SELECT/JOIN queries are allowed.",
            }

        allowed_tables = {
            config.form_54_table.lower(),
            config.form_55a_table.lower(),
            config.form_55_table.lower(),
            config.form_57_table.lower(),
            config.stb_1246_table.lower(),
        }
        lower_sql = cleaned.lower()
        if not any(tbl in lower_sql for tbl in allowed_tables):
            return {
                "error": "Query must reference at least one FRA table in users.neeraj_koul.",
                "hint": f"Allowed tables: {sorted(list(allowed_tables))}",
            }

        safe_limit = max(1, min(int(limit), 1000))
        qualified_sql = _qualify_fra_tables(cleaned)
        wrapped_sql = f"SELECT * FROM (\n{qualified_sql}\n) _fra_subq LIMIT {safe_limit + 1}"

        try:
            rows = execute_query(wrapped_sql)
            truncated = len(rows) > safe_limit
            if truncated:
                rows = rows[:safe_limit]

            cols = list(rows[0].keys()) if rows else []
            return {
                "unity_catalog_schema": f"{config.catalog}.{config.schema}",
                "row_count": len(rows),
                "limit_applied": safe_limit,
                "truncated": truncated,
                "truncation_note": (
                    f"Result set truncated at {safe_limit} rows; more matching rows exist in Unity Catalog. "
                    f"Increase `limit` (up to 1000), aggregate with GROUP BY, or add narrower WHERE filters."
                    if truncated
                    else "Complete result set returned (not truncated)."
                ),
                "columns": cols,
                "rows": rows,
                "sql_executed": f"SELECT * FROM (\n{qualified_sql}\n) _fra_subq LIMIT {safe_limit}",
            }
        except DatabaseQueryError as err:
            return {
                "error": err.message,
                "hint": (
                    f"{err.hint} | Key join columns: "
                    "form_54_accidents(incidentkey, accidentnumber, reportingrailroadcode, year, gxid, stateabbr, station, jointcd), "
                    "form_55a_casualties(incidentkey, incidentnumber, railroadcode, incidentyear, typeofperson, fatality, form54filed, form57filed), "
                    "form_57_crossings(gradecrossingid, incidentnumber, railroadcode, incidentyear, cityname, crossingwarning, form54filed)."
                ),
            }