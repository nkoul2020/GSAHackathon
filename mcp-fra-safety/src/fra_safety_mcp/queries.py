from typing import Any, Dict, List, Optional, Set, Tuple
from .db import DatabaseQueryError, resolve_col

_STATE_LOOKUP: Dict[str, Tuple[str, str]] = {
    "AL": ("ALABAMA", "01"), "AK": ("ALASKA", "02"), "AZ": ("ARIZONA", "04"), "AR": ("ARKANSAS", "05"),
    "CA": ("CALIFORNIA", "06"), "CO": ("COLORADO", "08"), "CT": ("CONNECTICUT", "09"), "DE": ("DELAWARE", "10"),
    "DC": ("DISTRICT OF COLUMBIA", "11"), "FL": ("FLORIDA", "12"), "GA": ("GEORGIA", "13"), "HI": ("HAWAII", "15"),
    "ID": ("IDAHO", "16"), "IL": ("ILLINOIS", "17"), "IN": ("INDIANA", "18"), "IA": ("IOWA", "19"),
    "KS": ("KANSAS", "20"), "KY": ("KENTUCKY", "21"), "LA": ("LOUISIANA", "22"), "ME": ("MAINE", "23"),
    "MD": ("MARYLAND", "24"), "MA": ("MASSACHUSETTS", "25"), "MI": ("MICHIGAN", "26"), "MN": ("MINNESOTA", "27"),
    "MS": ("MISSISSIPPI", "28"), "MO": ("MISSOURI", "29"), "MT": ("MONTANA", "30"), "NE": ("NEBRASKA", "31"),
    "NV": ("NEVADA", "32"), "NH": ("NEW HAMPSHIRE", "33"), "NJ": ("NEW JERSEY", "34"), "NM": ("NEW MEXICO", "35"),
    "NY": ("NEW YORK", "36"), "NC": ("NORTH CAROLINA", "37"), "ND": ("NORTH DAKOTA", "38"), "OH": ("OHIO", "39"),
    "OK": ("OKLAHOMA", "40"), "OR": ("OREGON", "41"), "PA": ("PENNSYLVANIA", "42"), "RI": ("RHODE ISLAND", "44"),
    "SC": ("SOUTH CAROLINA", "45"), "SD": ("SOUTH DAKOTA", "46"), "TN": ("TENNESSEE", "47"), "TX": ("TEXAS", "48"),
    "UT": ("UTAH", "49"), "VT": ("VERMONT", "50"), "VA": ("VIRGINIA", "51"), "WA": ("WASHINGTON", "53"),
    "WV": ("WEST VIRGINIA", "54"), "WI": ("WISCONSIN", "55"), "WY": ("WYOMING", "56"),
}


def resolve_year_expr(
    cols: Set[str],
    alias: str,
    year_candidates: Tuple[str, ...] = ("year", "accident_year", "incident_year", "year4", "iyr"),
    date_candidates: Tuple[str, ...] = ("date", "incident_date", "accident_date", "reporting_date"),
) -> str:
    all_year_cands = tuple(
        dict.fromkeys(
            year_candidates
            + ("year", "accident_year", "incident_year", "report_year", "calendar_year", "year4", "iyr")
        )
    )
    yr_col = resolve_col(cols, alias, all_year_cands, fallback_sql="NULL")
    if yr_col != "NULL":
        return f"CAST({yr_col} AS INT)"

    dt_col = resolve_col(cols, alias, date_candidates, fallback_sql="NULL")
    if dt_col != "NULL":
        return f"YEAR(CAST({dt_col} AS DATE))"

    raise DatabaseQueryError(
        "No year or date column found in table schema.",
        hint=f"Available columns include: {sorted(list(cols))[:25]}",
    )


def build_time_predicate(
    cols: Set[str],
    alias: str,
    prefix: str,
    params: Dict[str, Any],
    year_candidates: Tuple[str, ...],
    month_candidates: Tuple[str, ...],
    date_candidates: Tuple[str, ...],
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    year_type: str = "calendar",
    month: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    clauses: List[str] = []
    all_date_cands = tuple(
        dict.fromkeys(date_candidates + ("date", "incident_date", "accident_date", "reporting_date"))
    )
    all_month_cands = tuple(
        dict.fromkeys(
            month_candidates
            + ("accident_month", "incident_month", "report_month", "calendar_month", "month", "imo")
        )
    )

    yr_expr = resolve_year_expr(cols, alias, year_candidates, all_date_cands)
    dt_col = resolve_col(cols, alias, all_date_cands, fallback_sql="NULL")

    mo_col = resolve_col(cols, alias, all_month_cands, fallback_sql="NULL")
    if mo_col != "NULL":
        mo_expr = f"CAST({mo_col} AS INT)"
    elif dt_col != "NULL":
        mo_expr = f"MONTH(CAST({dt_col} AS DATE))"
    else:
        mo_expr = None

    if start_year is not None or end_year is not None:
        sy = start_year if start_year is not None else 2016
        ey = end_year if end_year is not None else 2026

        if year_type.strip().lower() == "fiscal" and mo_expr is not None:
            params[f"{prefix}_fy_s_prev"] = sy - 1
            params[f"{prefix}_fy_s"] = sy
            params[f"{prefix}_fy_e_prev"] = ey - 1
            params[f"{prefix}_fy_e"] = ey
            clauses.append(
                f"(({yr_expr} = %({prefix}_fy_s_prev)s AND {mo_expr} >= 10) "
                f"OR ({yr_expr} BETWEEN %({prefix}_fy_s)s AND %({prefix}_fy_e_prev)s) "
                f"OR ({yr_expr} = %({prefix}_fy_e)s AND {mo_expr} <= 9))"
            )
        else:
            params[f"{prefix}_yr_start"] = sy
            params[f"{prefix}_yr_end"] = ey
            clauses.append(f"{yr_expr} BETWEEN %({prefix}_yr_start)s AND %({prefix}_yr_end)s")

    if month is not None and mo_expr is not None:
        params[f"{prefix}_month"] = int(month)
        clauses.append(f"{mo_expr} = %({prefix}_month)s")

    if (start_date or end_date) and dt_col != "NULL":
        if start_date:
            params[f"{prefix}_start_dt"] = start_date
            clauses.append(f"CAST({dt_col} AS DATE) >= CAST(%({prefix}_start_dt)s AS DATE)")
        if end_date:
            params[f"{prefix}_end_dt"] = end_date
            clauses.append(f"CAST({dt_col} AS DATE) <= CAST(%({prefix}_end_dt)s AS DATE)")

    return " AND ".join(clauses) if clauses else "1=1"


def build_common_filters(
    cols: Set[str],
    alias: str,
    prefix: str,
    params: Dict[str, Any],
    include_geo: bool = True,
    state: Optional[str] = None,
    county: Optional[str] = None,
    city: Optional[str] = None,
    fra_region: Optional[str] = None,
    smt: Optional[str] = None,
    railroad_code: Optional[str] = None,
    parent_railroad_code: Optional[str] = None,
    railroad_class: Optional[str] = None,
    railroad_group: Optional[str] = None,
) -> str:
    clauses: List[str] = []

    if railroad_code:
        rr_col = resolve_col(cols, alias, ("reporting_railroad_code", "railroad_code", "railroad"))
        params[f"{prefix}_rr"] = railroad_code.strip().upper()
        clauses.append(f"UPPER(TRIM(CAST({rr_col} AS STRING))) = %({prefix}_rr)s")

    if parent_railroad_code:
        prr_col = resolve_col(
            cols,
            alias,
            ("reporting_parent_railroad_code", "parent_railroad_code", "parent_railroad", "sys_rr"),
        )
        params[f"{prefix}_prr"] = parent_railroad_code.strip().upper()
        clauses.append(f"UPPER(TRIM(CAST({prr_col} AS STRING))) = %({prefix}_prr)s")

    if railroad_class:
        cls_col = resolve_col(
            cols, alias, ("reporting_railroad_class", "railroad_class", "class_code", "rr_class"), fallback_sql="NULL"
        )
        if cls_col != "NULL":
            params[f"{prefix}_cls"] = f"%{railroad_class.strip().upper()}%"
            clauses.append(f"UPPER(CAST({cls_col} AS STRING)) LIKE %({prefix}_cls)s")

    if railroad_group:
        grp_col = resolve_col(
            cols,
            alias,
            ("reporting_railroad_holding_company", "reporting_railroad_group", "railroad_group", "holding_company"),
            fallback_sql="NULL",
        )
        if grp_col != "NULL":
            params[f"{prefix}_grp"] = f"%{railroad_group.strip().upper()}%"
            clauses.append(f"UPPER(CAST({grp_col} AS STRING)) LIKE %({prefix}_grp)s")

    if fra_region:
        reg_col = resolve_col(
            cols, alias, ("fra_region", "region", "reporting_railroad_region", "district"), fallback_sql="NULL"
        )
        if reg_col != "NULL":
            params[f"{prefix}_reg"] = str(fra_region).strip()
            clauses.append(f"TRIM(CAST({reg_col} AS STRING)) = %({prefix}_reg)s")

    if smt:
        smt_col = resolve_col(
            cols,
            alias,
            ("reporting_railroad_smt_grouping", "smt", "reporting_railroad_smt", "safety_management_team"),
            fallback_sql="NULL",
        )
        if smt_col != "NULL":
            params[f"{prefix}_smt"] = smt.strip().upper()
            clauses.append(f"UPPER(TRIM(CAST({smt_col} AS STRING))) = %({prefix}_smt)s")

    if include_geo:
        if state:
            st_raw = state.strip().upper()
            st_full, st_fips = _STATE_LOOKUP.get(st_raw, (st_raw, st_raw))
            params[f"{prefix}_st_abbr"] = st_raw
            params[f"{prefix}_st_full"] = st_full
            params[f"{prefix}_st_fips"] = st_fips

            st_abbr_col = resolve_col(cols, alias, ("state_abbr", "state"), fallback_sql="NULL")
            st_name_col = resolve_col(cols, alias, ("state_name", "state_abbr", "state"), fallback_sql="NULL")
            st_code_col = resolve_col(cols, alias, ("state_code", "st"), fallback_sql="NULL")

            st_parts: List[str] = []
            if st_abbr_col != "NULL":
                st_parts.append(
                    f"UPPER(TRIM(CAST({st_abbr_col} AS STRING))) IN (%({prefix}_st_abbr)s, %({prefix}_st_full)s)"
                )
            if st_name_col != "NULL" and st_name_col != st_abbr_col:
                st_parts.append(
                    f"UPPER(TRIM(CAST({st_name_col} AS STRING))) IN (%({prefix}_st_abbr)s, %({prefix}_st_full)s)"
                )
            if st_code_col != "NULL" and st_code_col not in (st_abbr_col, st_name_col):
                st_parts.append(
                    f"LPAD(TRIM(CAST({st_code_col} AS STRING)), 2, '0') = %({prefix}_st_fips)s "
                    f"OR UPPER(TRIM(CAST({st_code_col} AS STRING))) = %({prefix}_st_abbr)s"
                )
            if st_parts:
                clauses.append(f"({' OR '.join(st_parts)})")

        if county:
            cnty_col = resolve_col(cols, alias, ("county_name", "county", "cnty"))
            params[f"{prefix}_county"] = f"%{county.strip().upper()}%"
            clauses.append(f"UPPER(CAST({cnty_col} AS STRING)) LIKE %({prefix}_county)s")

        if city:
            city_col = resolve_col(
                cols,
                alias,
                ("city_name", "city", "station", "nearest_station", "nearest_city_and_town"),
                fallback_sql="NULL",
            )
            if city_col != "NULL":
                params[f"{prefix}_city"] = f"%{city.strip().upper()}%"
                clauses.append(f"UPPER(CAST({city_col} AS STRING)) LIKE %({prefix}_city)s")

    return (" AND " + " AND ".join(clauses)) if clauses else ""


def build_form54_filters(
    cols: Set[str],
    alias: str,
    prefix: str,
    params: Dict[str, Any],
    include_crossings: bool = False,
    accident_type: Optional[str] = None,
    cause_category: Optional[str] = None,
    cause_code_prefix: Optional[str] = None,
    track_type: Optional[str] = None,
    track_class: Optional[str] = None,
    method_of_operation: Optional[str] = None,
    hazmat_only: bool = False,
) -> str:
    clauses: List[str] = []
    typ_code_col = resolve_col(cols, alias, ("accident_type_code", "typacc", "accident_type"), fallback_sql="NULL")
    typ_text_col = resolve_col(cols, alias, ("accident_type", "accident_type_code", "typacc"), fallback_sql="NULL")

    if not include_crossings and typ_code_col != "NULL":
        clauses.append(
            f"(TRIM(CAST({typ_code_col} AS STRING)) != '7' "
            f"AND UPPER(CAST({typ_text_col} AS STRING)) NOT LIKE '%HIGHWAY-RAIL%' "
            f"AND UPPER(CAST({typ_text_col} AS STRING)) NOT LIKE '%CROSSING%')"
        )

    if accident_type and typ_code_col != "NULL":
        params[f"{prefix}_acctyp"] = f"%{accident_type.strip().upper()}%"
        clauses.append(
            f"(UPPER(CAST({typ_code_col} AS STRING)) LIKE %({prefix}_acctyp)s "
            f"OR UPPER(CAST({typ_text_col} AS STRING)) LIKE %({prefix}_acctyp)s)"
        )

    cause_col = resolve_col(
        cols, alias, ("primary_accident_cause_code", "accident_cause_code", "cause"), fallback_sql="NULL"
    )
    if cause_category and cause_col != "NULL":
        params[f"{prefix}_ccat"] = f"{cause_category.strip().upper()[:1]}%"
        clauses.append(f"UPPER(TRIM(CAST({cause_col} AS STRING))) LIKE %({prefix}_ccat)s")

    if cause_code_prefix and cause_col != "NULL":
        params[f"{prefix}_cpfx"] = f"{cause_code_prefix.strip().upper()}%"
        clauses.append(f"UPPER(TRIM(CAST({cause_col} AS STRING))) LIKE %({prefix}_cpfx)s")

    if track_type:
        trk_code_col = resolve_col(cols, alias, ("track_type_code", "typtrk", "track_type"), fallback_sql="NULL")
        trk_text_col = resolve_col(cols, alias, ("track_type", "track_type_code", "typtrk"), fallback_sql="NULL")
        if trk_code_col != "NULL":
            params[f"{prefix}_trktyp"] = f"%{track_type.strip().upper()}%"
            clauses.append(
                f"(UPPER(CAST({trk_code_col} AS STRING)) LIKE %({prefix}_trktyp)s "
                f"OR UPPER(CAST({trk_text_col} AS STRING)) LIKE %({prefix}_trktyp)s)"
            )

    if track_class:
        tcls_col = resolve_col(cols, alias, ("track_class", "trkclas"), fallback_sql="NULL")
        if tcls_col != "NULL":
            params[f"{prefix}_trkcls"] = track_class.strip().upper()
            clauses.append(f"UPPER(TRIM(CAST({tcls_col} AS STRING))) = %({prefix}_trkcls)s")

    if method_of_operation:
        mop_code_col = resolve_col(cols, alias, ("method_of_operation_code", "mthdopr", "method_of_operation"), fallback_sql="NULL")
        mop_text_col = resolve_col(cols, alias, ("method_of_operation", "method_of_operation_code", "mthdopr"), fallback_sql="NULL")
        if mop_code_col != "NULL":
            params[f"{prefix}_mop"] = f"%{method_of_operation.strip().upper()}%"
            clauses.append(
                f"(UPPER(CAST({mop_code_col} AS STRING)) LIKE %({prefix}_mop)s "
                f"OR UPPER(CAST({mop_text_col} AS STRING)) LIKE %({prefix}_mop)s)"
            )

    if hazmat_only:
        hz_col = resolve_col(
            cols,
            alias,
            ("hazmat_cars_damaged", "hazmat_cars_damaged_derailed", "carsdmg", "hazmat_released_cars", "carshzd"),
            fallback_sql="NULL",
        )
        if hz_col != "NULL":
            clauses.append(f"COALESCE(CAST({hz_col} AS INT), 0) > 0")

    return (" AND " + " AND ".join(clauses)) if clauses else ""


def build_form57_filters(
    cols: Set[str],
    alias: str,
    prefix: str,
    params: Dict[str, Any],
    crossing_type: Optional[str] = None,
    highway_user: Optional[str] = None,
    warning_device: Optional[str] = None,
    struck_by: Optional[str] = None,
    crossing_id: Optional[str] = None,
) -> str:
    clauses: List[str] = []

    if crossing_type:
        ct_col = resolve_col(
            cols, alias, ("public_private", "public_private_code", "crossing_type"), fallback_sql="NULL"
        )
        if ct_col != "NULL":
            params[f"{prefix}_xtype"] = f"%{crossing_type.strip().upper()}%"
            clauses.append(f"UPPER(CAST({ct_col} AS STRING)) LIKE %({prefix}_xtype)s")

    if highway_user:
        hu_col = resolve_col(
            cols, alias, ("highway_user", "highway_user_code", "typveh"), fallback_sql="NULL"
        )
        if hu_col != "NULL":
            params[f"{prefix}_huser"] = f"%{highway_user.strip().upper()}%"
            clauses.append(f"UPPER(CAST({hu_col} AS STRING)) LIKE %({prefix}_huser)s")

    if warning_device:
        wd_col = resolve_col(
            cols,
            alias,
            ("crossing_warning", "crossing_warning_code", "warning_device", "wdcode"),
            fallback_sql="NULL",
        )
        if wd_col != "NULL":
            params[f"{prefix}_wdev"] = f"%{warning_device.strip().upper()}%"
            clauses.append(f"UPPER(CAST({wd_col} AS STRING)) LIKE %({prefix}_wdev)s")

    if struck_by:
        sb_col = resolve_col(
            cols, alias, ("equipment_struck", "equipment_struck_code", "struck_by", "typacci"), fallback_sql="NULL"
        )
        if sb_col != "NULL":
            sb_norm = struck_by.strip().lower()
            if "train" in sb_norm and "highway" not in sb_norm:
                clauses.append(
                    f"(TRIM(CAST({sb_col} AS STRING)) = '1' OR UPPER(CAST({sb_col} AS STRING)) LIKE '%STRUCK HIGHWAY%')"
                )
            elif "highway" in sb_norm or "user" in sb_norm or "vehicle" in sb_norm:
                clauses.append(
                    f"(TRIM(CAST({sb_col} AS STRING)) = '2' OR UPPER(CAST({sb_col} AS STRING)) LIKE '%STRUCK RAIL%')"
                )
            else:
                params[f"{prefix}_sby"] = f"%{struck_by.strip().upper()}%"
                clauses.append(f"UPPER(CAST({sb_col} AS STRING)) LIKE %({prefix}_sby)s")

    if crossing_id:
        xid_col = resolve_col(
            cols,
            alias,
            ("grade_crossing_id", "crossing_id", "gxid", "usdot_crossing_id"),
            fallback_sql="NULL",
        )
        if xid_col != "NULL":
            params[f"{prefix}_xid"] = crossing_id.strip().upper()
            clauses.append(f"UPPER(TRIM(CAST({xid_col} AS STRING))) = %({prefix}_xid)s")

    return (" AND " + " AND ".join(clauses)) if clauses else ""


def build_form55a_filters(
    cols: Set[str],
    alias: str,
    prefix: str,
    params: Dict[str, Any],
    person_type: Optional[str] = None,
    severity: Optional[str] = None,
) -> str:
    clauses: List[str] = []

    if person_type:
        pt_col = resolve_col(
            cols, alias, ("type_of_person", "type_of_person_code", "person_type", "typperson"), fallback_sql="NULL"
        )
        if pt_col != "NULL":
            params[f"{prefix}_ptype"] = f"%{person_type.strip().upper()}%"
            clauses.append(f"UPPER(CAST({pt_col} AS STRING)) LIKE %({prefix}_ptype)s")

    if severity:
        fat_col = resolve_col(cols, alias, ("fatality", "ifatal", "fatal", "killed"), fallback_sql="NULL")
        if fat_col != "NULL":
            sev = severity.strip().lower()
            if sev == "fatal":
                clauses.append(f"UPPER(TRIM(CAST({fat_col} AS STRING))) IN ('Y', 'YES', '1', 'TRUE')")
            elif sev == "nonfatal":
                clauses.append(
                    f"UPPER(TRIM(CAST({fat_col} AS STRING))) NOT IN ('Y', 'YES', '1', 'TRUE')"
                )

    return (" AND " + " AND ".join(clauses)) if clauses else ""
