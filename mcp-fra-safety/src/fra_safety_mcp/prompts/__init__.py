from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register reusable multi-step FRA and STB safety investigation prompts."""

    @mcp.prompt()
    def metro_safety_audit_briefing(
        city: str,
        state: str = "",
        start_year: int = 2016,
        end_year: int = 2025,
    ) -> str:
        """Conducts a 49 CFR Part 225-compliant cross-portal safety audit for a U.S. metro area.

        Args:
            city: Target U.S. city or station name (e.g., 'Chicago', 'Houston').
            state: Optional two-letter state abbreviation or full state name (e.g., 'IL', 'TX').
            start_year: First calendar year to include (default 2016).
            end_year: Last calendar year to include (default 2025).
        """
        scope = f"{city}, {state}" if state else city
        state_arg = f", state={state!r}" if state else ""
        return (
            f"Conduct an executive FRA rail safety briefing for {scope} ({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reference/preparing-reports-guide` and `fra://reports/1.12-methodology` "
            "to ensure proper 49 CFR Part 225 deduplication and geographic rate rules.\n"
            f"2. Call `analyze_metro_corridor_safety(cities=[{city!r}]{state_arg}, "
            f"start_year={start_year}, end_year={end_year})` to gather Form 54 accidents, Form 55a "
            "casualties, and Form 57 grade crossing counts.\n"
            f"3. Call `get_train_accident_summary(city={city!r}{state_arg}, start_year={start_year}, "
            f"end_year={end_year}, include_crossings=False, group_by='cause_group')` (Report 2.03) "
            "to identify top Appendix C cause categories (H/T/E/S/M).\n"
            f"4. Call `analyze_highway_rail_crossings(city={city!r}{state_arg}, start_year={start_year}, "
            f"end_year={end_year}, report_view='crossing_hotspots', limit=10)` to pinpoint repeat-incident "
            "USDOT National Crossing Inventory IDs.\n"
            "5. Present an executive summary table, highlight top risk drivers, and recommend two targeted "
            "infrastructure or operational interventions. Do NOT compute train-mile or employee-hour rates, "
            "as Form 55 exposure is reported at the railroad level rather than by city or state."
        )

    @mcp.prompt()
    def railroad_system_safety_scorecard(
        parent_railroad_code: str,
        start_year: int = 2020,
        end_year: int = 2025,
        year_type: str = "calendar",
    ) -> str:
        """Generates a normalized FRA Report 1.12 & 3.10 safety scorecard for a Parent Railroad system.

        Args:
            parent_railroad_code: Parent holding/system railroad code (e.g., 'BNSF', 'UP', 'NS', 'CSX').
            start_year: First year to include (default 2020).
            end_year: Last year to include (default 2025).
            year_type: 'calendar' (Jan–Dec) or 'fiscal' (Federal FY Oct–Sep).
        """
        return (
            f"Generate an official FRA normalized safety scorecard for parent railroad system "
            f"`{parent_railroad_code}` ({start_year}–{end_year}, {year_type} year).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/1.12-methodology` and `fra://reference/filter-glossary`, and call "
            "`audit_delta_table_versions()` to record Unity Catalog table lineage.\n"
            f"2. Call `get_report_1_12_rail_safety_overview(start_year={start_year}, end_year={end_year}, "
            f"year_type={year_type!r}, parent_railroad_code={parent_railroad_code!r})` for cross-form "
            "counts and Form 55 normalized rates.\n"
            f"3. Call `get_train_accident_summary(start_year={start_year}, end_year={end_year}, "
            f"year_type={year_type!r}, parent_railroad_code={parent_railroad_code!r}, "
            "include_crossings=True, table_view='table1_macro', group_by='year')` (Report 3.10) to show "
            "the annual trend across all carrier involvements (jointcd 1, 2, and 3).\n"
            f"4. Call `get_train_accident_summary(start_year={start_year}, end_year={end_year}, "
            f"year_type={year_type!r}, parent_railroad_code={parent_railroad_code!r}, "
            "include_crossings=False, table_view='table2_railroad', group_by='railroad')` (Report 2.03) "
            "to break out subsidiary operating carriers.\n"
            f"5. Call `audit_joint_track_cause_discrepancies(start_year={start_year}, end_year={end_year}, "
            f"year_type={year_type!r}, parent_railroad_code={parent_railroad_code!r}, limit=10)`.\n"
            "6. Report both Report 2.03 (non-crossing) and Report 3.10 (including crossings) accident totals, "
            "train-mile normalized rates, employee on-duty rates per 200,000 hours, subsidiary carrier "
            "contributions, and high-damage joint-track cause discrepancies."
        )

    @mcp.prompt()
    def railroad_workforce_and_safety_briefing(
        parent_railroad_code: str = "BNSF",
        start_year: int = 2020,
        end_year: int = 2025,
    ) -> str:
        """Synthesizes FRA safety performance (Forms 54/55/55a) with STB workforce trends for a Class I carrier.

        Args:
            parent_railroad_code: Parent Class I railroad code (e.g., 'BNSF', 'UP', 'NS', 'CSX').
            start_year: First calendar year to include (default 2020).
            end_year: Last calendar year to include (default 2025).
        """
        return (
            f"Prepare a cross-agency FRA + Surface Transportation Board (STB) safety and workforce briefing "
            f"for `{parent_railroad_code}` ({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/1.12-methodology` and `fra://reference/preparing-reports-guide`.\n"
            f"2. Call `get_report_1_12_rail_safety_overview(start_year={start_year}, end_year={end_year}, "
            f"parent_railroad_code={parent_railroad_code!r})` to retrieve FRA train accidents, employee "
            "on-duty casualties, train-miles, and employee hours worked.\n"
            f"3. Call `get_train_accident_summary(start_year={start_year}, end_year={end_year}, "
            f"parent_railroad_code={parent_railroad_code!r}, include_crossings=True, group_by='year')` "
            "to capture annual Report 3.10 accident trends.\n"
            "4. Query Surface Transportation Board employment data (`stb_1246_employment` via the STB "
            f"employment tool or `run_fra_sql_query`) for `{parent_railroad_code}` across "
            f"{start_year}–{end_year} to retrieve headcount by employee group (e.g., Train & Engine, "
            "Maintenance of Way, Maintenance of Equipment).\n"
            "5. Compare annual STB staffing shifts against FRA train-mile volume, Human Factor (`H`) and "
            "Track (`T`) accident rates, and employee on-duty casualty rates per 200,000 hours."
        )

    @mcp.prompt()
    def grade_crossing_hotspot_audit(
        state: str,
        start_year: int = 2020,
        end_year: int = 2025,
    ) -> str:
        """Investigates state-level highway-rail grade crossing risks across warning devices, road users, and USDOT IDs.

        Args:
            state: State abbreviation or full name (e.g., 'TX', 'CA', 'IL').
            start_year: First calendar year to include (default 2020).
            end_year: Last calendar year to include (default 2025).
        """
        return (
            f"Perform a comprehensive Form 57 highway-rail grade crossing safety analysis for `{state}` "
            f"({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/form57-crossings-methodology`.\n"
            f"2. Call `analyze_highway_rail_crossings(state={state!r}, start_year={start_year}, "
            f"end_year={end_year}, report_view='warning_device_2_08')` (Report 2.08).\n"
            f"3. Call `analyze_highway_rail_crossings(state={state!r}, start_year={start_year}, "
            f"end_year={end_year}, report_view='highway_user_5_14')` (Report 5.14).\n"
            f"4. Call `analyze_highway_rail_crossings(state={state!r}, start_year={start_year}, "
            f"end_year={end_year}, report_view='crossing_hotspots', limit=15)` to rank the highest-frequency "
            "USDOT Crossing IDs.\n"
            "5. For the top 2 hotspot `usdot_crossing_id` values, call `walk_across_fra_forms(crossing_id=..., "
            f"start_year={start_year}, end_year={end_year})` to check whether any crossing collisions also "
            "triggered Form 54 train accident or Form 55a casualty filings.\n"
            "6. Summarize fatalities, injuries, passive vs. active warning device exposure, and top candidate "
            "crossings for Section 130 grade-separation or gate-upgrade funding."
        )

    @mcp.prompt()
    def joint_track_discrepancy_review(
        start_year: int = 2020,
        end_year: int = 2025,
        state: str = "",
        parent_railroad_code: str = "",
    ) -> str:
        """Audits multi-carrier Form 54 collisions where primary and secondary railroads reported conflicting cause codes.

        Args:
            start_year: First calendar year to include (default 2020).
            end_year: Last calendar year to include (default 2025).
            state: Optional state filter (e.g., 'IL', 'TX').
            parent_railroad_code: Optional parent railroad filter (e.g., 'BNSF', 'UP') matching primary or secondary filings.
        """
        scope_parts = []
        if parent_railroad_code:
            scope_parts.append(f"involving `{parent_railroad_code}`")
        if state:
            scope_parts.append(f"in `{state}`")
        scope = (" ".join(scope_parts) + " ") if scope_parts else "nationwide "

        extra_args = ""
        if state:
            extra_args += f", state={state!r}"
        if parent_railroad_code:
            extra_args += f", parent_railroad_code={parent_railroad_code!r}"

        return (
            f"Conduct a regulatory discrepancy audit of joint-operations Form 54 accidents {scope}"
            f"({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/train-accidents-methodology` and `fra://reference/cause-code-categories`.\n"
            f"2. Call `audit_joint_track_cause_discrepancies(start_year={start_year}, end_year={end_year}"
            f"{extra_args}, only_mismatched_causes=True, limit=25)`.\n"
            "3. Group the mismatches by Appendix C cause category shifts (e.g., primary carrier citing "
            "Track `T` vs. secondary carrier citing Human Factors `H`) and flag incidents with large "
            "reported train-speed discrepancies for FRA safety inspector follow-up."
        )