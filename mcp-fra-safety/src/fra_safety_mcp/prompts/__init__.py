from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register reusable multi-step FRA safety investigation and briefing prompts."""

    @mcp.prompt()
    def metro_safety_audit_briefing(
        city: str,
        state: str = "",
        start_year: int = 2016,
        end_year: int = 2025,
    ) -> str:
        """Conducts a 49 CFR Part 225-compliant cross-portal safety audit for a U.S. metro area."""
        scope = f"{city}, {state}" if state else city
        state_arg = f", state='{state}'" if state else ""
        return (
            f"Conduct an executive FRA rail safety briefing for {scope} ({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reference/preparing-reports-guide` and `fra://reports/1.12-methodology` "
            "to ensure proper 49 CFR Part 225 deduplication and geographic rate rules.\n"
            f"2. Call `analyze_metro_corridor_safety(cities=['{city}']{state_arg}, "
            f"start_year={start_year}, end_year={end_year})` to gather Form 54 accidents, Form 55a "
            "casualties, and Form 57 grade crossing counts.\n"
            f"3. Call `get_train_accident_summary(city='{city}'{state_arg}, start_year={start_year}, "
            f"end_year={end_year}, group_by='cause_group')` to identify top Appendix C cause categories (H/T/E/S/M).\n"
            f"4. Call `analyze_highway_rail_crossings(city='{city}'{state_arg}, start_year={start_year}, "
            f"end_year={end_year}, report_view='crossing_hotspots', limit=10)` to pinpoint repeat-incident "
            "USDOT National Crossing Inventory IDs.\n"
            "5. Present an executive summary table, highlight top risk drivers, and recommend two targeted "
            "infrastructure or operational interventions."
        )

    @mcp.prompt()
    def railroad_system_safety_scorecard(
        parent_railroad_code: str,
        start_year: int = 2020,
        end_year: int = 2025,
        year_type: str = "calendar",
    ) -> str:
        """Generates a normalized FRA Report 1.12 safety scorecard for a Class I or Parent Railroad system."""
        return (
            f"Generate an official FRA Report 1.12 normalized safety scorecard for parent railroad system "
            f"`{parent_railroad_code}` ({start_year}–{end_year}, {year_type} year).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/1.12-methodology` and `fra://reference/filter-glossary`.\n"
            f"2. Call `get_report_1_12_rail_safety_overview(start_year={start_year}, end_year={end_year}, "
            f"year_type='{year_type}', parent_railroad_code='{parent_railroad_code}')`.\n"
            f"3. Call `get_train_accident_summary(start_year={start_year}, end_year={end_year}, "
            f"year_type='{year_type}', parent_railroad_code='{parent_railroad_code}', "
            "table_view='table2_railroad', group_by='railroad')` to break out subsidiary operating carriers.\n"
            f"4. Call `audit_joint_track_cause_discrepancies(start_year={start_year}, end_year={end_year}, "
            f"year_type='{year_type}', parent_railroad_code='{parent_railroad_code}', limit=10)`.\n"
            "5. Report train-mile normalized accident/crossing rates, employee on-duty rates per 200,000 hours, "
            "subsidiary carrier contributions, and any high-damage joint-track cause discrepancies."
        )

    @mcp.prompt()
    def grade_crossing_hotspot_audit(
        state: str,
        start_year: int = 2020,
        end_year: int = 2025,
    ) -> str:
        """Investigates state-level highway-rail grade crossing risks across warning devices, road users, and USDOT IDs."""
        return (
            f"Perform a comprehensive Form 57 highway-rail grade crossing safety analysis for `{state}` "
            f"({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/form57-crossings-methodology`.\n"
            f"2. Call `analyze_highway_rail_crossings(state='{state}', start_year={start_year}, "
            f"end_year={end_year}, report_view='warning_device_2_08')` (Report 2.08).\n"
            f"3. Call `analyze_highway_rail_crossings(state='{state}', start_year={start_year}, "
            f"end_year={end_year}, report_view='highway_user_5_14')` (Report 5.14).\n"
            f"4. Call `analyze_highway_rail_crossings(state='{state}', start_year={start_year}, "
            f"end_year={end_year}, report_view='crossing_hotspots', limit=15)` to rank the highest-frequency "
            "USDOT Crossing IDs.\n"
            "5. Summarize fatalities, injuries, passive vs. active warning device exposure, and top candidate "
            "crossings for Section 130 grade-separation or gate-upgrade funding."
        )

    @mcp.prompt()
    def joint_track_discrepancy_review(
        start_year: int = 2020,
        end_year: int = 2025,
        state: str = "",
    ) -> str:
        """Audits multi-carrier Form 54 collisions where primary and secondary railroads reported conflicting cause codes."""
        scope = f"in `{state}` " if state else "nationwide "
        state_arg = f", state='{state}'" if state else ""
        return (
            f"Conduct a regulatory discrepancy audit of joint-operations Form 54 accidents {scope}"
            f"({start_year}–{end_year}).\n\n"
            "Follow these steps strictly:\n"
            "1. Read `fra://reports/train-accidents-methodology` and `fra://reference/cause-code-categories`.\n"
            f"2. Call `audit_joint_track_cause_discrepancies(start_year={start_year}, end_year={end_year}"
            f"{state_arg}, only_mismatched_causes=True, limit=25)`.\n"
            "3. Group the mismatches by Appendix C cause category shifts (e.g., primary carrier citing "
            "Track `T` vs. secondary carrier citing Human Factors `H`) and flag incidents with large "
            "reported train-speed discrepancies for FRA safety inspector follow-up."
        )