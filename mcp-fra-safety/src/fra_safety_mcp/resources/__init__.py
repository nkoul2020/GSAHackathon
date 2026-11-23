from fastmcp import FastMCP


def register_resources(mcp: FastMCP) -> None:
    """Register all official FRA 49 CFR Part 225 reference and methodology resources."""

    @mcp.resource("fra://reference/preparing-reports-guide")
    def fra_preparing_reports_guide() -> str:
        """
        Official reference metadata and reporting rules from the FRA Guide for
        Preparing Accident/Incident Reports (49 CFR Part 225) covering Forms 54, 55, 55a, and 57.
        """
        return (
            "Official Reference: FRA Guide for Preparing Accident/Incident Reports\n"
            "Publisher: Federal Railroad Administration (FRA), Office of Railroad Safety\n"
            "Authority: Title 49, Code of Federal Regulations (49 CFR) Part 225\n"
            "URL: https://railroads.dot.gov/elibrary/fra-guide-preparing-accidentincident-reports-0\n\n"
            "Key Reporting & Data Interpretation Rules Across All 4 FRA Datasets:\n"
            "1. Chapter 5 — Form FRA F 6180.55 (Railroad Injury and Illness Summary / Operational Data):\n"
            "   - Monthly railroad-level operational exposure denominator dataset: total train-miles,\n"
            "     main line miles, yard switching miles, employee hours worked, and passengers transported.\n"
            "   - Reported at the Railroad/System level (not disaggregated by state, county, or city).\n"
            "2. Chapter 6 — Form FRA F 6180.55a (Injury/Illness Continuation Sheet):\n"
            "   - Logs all reportable fatalities, nonfatal injuries, and occupational illnesses across\n"
            "     employees on duty, passengers, trespassers, and nontrespassers (including events that\n"
            "     did not involve a Form 54 equipment accident).\n"
            "3. Chapter 7 — Form FRA F 6180.54 (Rail Equipment Accident/Incident Report):\n"
            "   - Every railroad whose on-track equipment was involved AND the railroad responsible\n"
            "     for track maintenance must file Form 54 under a shared `incidentkey`.\n"
            "   - `jointcd = '1'` designates the single primary record for national accident counts;\n"
            "     `jointcd = '2'` marks secondary involved railroads; `jointcd = '3'` marks overflow consist sheets.\n"
            "   - Total accident property damage is the SUM of `totaldamagecost` across all reports\n"
            "     filed under the same `incidentkey` (`jointcd` 1, 2, and 3).\n"
            "4. Chapter 10 — Form FRA F 6180.57 (Highway-Rail Grade Crossing Accident/Incident Report):\n"
            "   - Logs all collisions/impacts between on-track rail equipment and highway users at public\n"
            "     or private grade crossings regardless of dollar damage.\n"
            "   - Dual-Reporting Rule: If a grade crossing collision ALSO causes rail equipment or track\n"
            "     damage exceeding the Part 225 monetary reporting threshold, the railroad must file BOTH\n"
            "     a Form 57 AND a Form 54. Standard train accident summaries (Report 2.03) exclude\n"
            "     crossing events to avoid double-counting across portals.\n"
        )

    @mcp.resource("fra://reports/1.12-methodology")
    def report_112_methodology() -> str:
        """Official methodology for FRA Report 1.12: Rail Safety Overview (portal dsuf-xcni)."""
        return (
            "FRA Report 1.12 — Rail Safety Overview Report (dsuf-xcni) Methodology:\n"
            "1. Cross-Form Integration (All 4 Tables):\n"
            "   - Combines Form 54 (train accidents not at crossings), Form 57 (highway-rail grade\n"
            "     crossing incidents), Form 55a (casualties), and Form 55 (operational exposure).\n"
            "2. Official Rate Normalization Formulas:\n"
            "   - Rate of Total Acc/Inc per Million Train-Miles = (Total Acc/Inc / Total Train-Miles) * 1,000,000\n"
            "   - Rate of Train Accidents per Million Train-Miles = (Form 54 Deduplicated Accidents / Total Train-Miles) * 1,000,000\n"
            "   - Rate of Highway-Rail Incidents per Million Train-Miles = (Form 57 Incidents / Total Train-Miles) * 1,000,000\n"
            "   - Rate of Employees on Duty per 200K Hours = (Employee Casualties / Employee Hours Worked) * 200,000\n"
            "   - Public Crossing Share (%) = (Public Crossing Incidents / Total Crossing Incidents) * 100\n"
            "3. Primary vs. All-Railroad Aggregation on Form 54:\n"
            "   - Accident counts, cause groups (H/T/E/S/M), and track types (Main/Yard/Siding/Industry)\n"
            "     come from the primary `jointcd = '1'` record (excluding highway-rail crossings).\n"
            "   - Property damage cost, hazmat cars damaged/derailed, fatalities, and injuries sum across\n"
            "     all reports (`jointcd` 1, 2, 3) sharing the same `incidentkey`.\n"
            "4. Blank Operational/Rate Rows Under Geographic Filters (Exact FRA Portal Parity):\n"
            "   - Form 55 operational exposure is U.S./Railroad-level only. Whenever a State, County, or\n"
            "     City filter is active, incident and casualty counts remain valid, while 10 operational\n"
            "     and rate metrics intentionally return null/blank: Number of Railroads Included,\n"
            "     Total Train-Miles, Main Line Miles, Yard Switching Miles, Employee Hours Worked,\n"
            "     Passengers Transported, and all 4 per-train-mile or per-200K-hour rates.\n"
        )

    @mcp.resource("fra://reports/train-accidents-methodology")
    def train_accidents_methodology() -> str:
        """Official methodology for FRA Train Accident Reports 2.03, 3.10, and 3.18 (portal wjun-6kqb)."""
        return (
            "FRA Train Accident Summary Rules (Reports 2.03, 3.10, and 3.18 — portal wjun-6kqb):\n"
            "1. Crossing Exclusion vs. Inclusion:\n"
            "   - Report 2.03 (Train Accidents NOT at Highway-Rail Crossings): Excludes highway-rail\n"
            "     crossing accidents (`include_crossings = False`). Standard FRA headline accident count.\n"
            "   - Report 3.10 (Train Accidents INCLUDING Highway-Rail Crossings): Includes crossing\n"
            "     collisions that exceeded the Form 54 monetary damage threshold (`include_crossings = True`).\n"
            "2. Table 1 vs. Table 2 Deduplication (Report 2.03 & Report 3.18):\n"
            "   - Table 1 (Macro/U.S./State/Category view): Deduplicates multi-train crashes via `incidentkey`\n"
            "     and `jointcd = '1'`, summing `totaldamagecost` across all reports (`jointcd` 1, 2, 3).\n"
            "   - Table 2 (Individual Railroad view): Counts distinct `incidentkey`s where each railroad was\n"
            "     involved (`jointcd` 1 or 2). Because two railroads can be involved in one collision, individual\n"
            "     railroad rows overlap and sum to MORE than the deduplicated Grand Total row.\n"
            "3. Joint-Track Cause Discrepancy Audits (`jointcd = '1'` vs. `jointcd = '2'`):\n"
            "   - On shared trackage or multi-carrier collisions, the primary railroad (`jointcd = '1'`) and\n"
            "     secondary railroad (`jointcd = '2'`) file separate Form 54 reports under the same `incidentkey`\n"
            "     and frequently report differing primary cause codes or train speeds.\n"
            "4. Timeframe Support: Calendar Year (Jan–Dec) and Federal Fiscal Year (Oct 1–Sep 30).\n"
        )

    @mcp.resource("fra://reports/form57-crossings-methodology")
    def form57_crossings_methodology() -> str:
        """Official methodology for Form 57 Highway-Rail Grade Crossing Reports (portal 9hnw-nt86)."""
        return (
            "FRA Form 57 — Highway-Rail Grade Crossing Reports (1.11, 2.08, 5.14, 5.15 — portal 9hnw-nt86):\n"
            "1. Core Reports Covered:\n"
            "   - Report 1.11: Highway-Rail Crossing Incident Summary (incidents, fatalities, injuries).\n"
            "   - Report 2.08: Highway-Rail Incidents by Warning Device & Crossing Type (Public vs. Private).\n"
            "   - Report 5.14: Highway-Rail Incidents by Highway User Type (Auto, Truck, Truck-Trailer,\n"
            "     Pedestrian, Motorcycle, Bus, Other).\n"
            "   - Report 5.15: Highway-Rail Incidents by Struck-By Direction (Train struck highway user\n"
            "     vs. Highway user struck train).\n"
            "2. USDOT National Crossing Inventory ID (`crossing_id` / `gxid`):\n"
            "   - Every public and private crossing has a unique 6-digit + check-letter USDOT ID.\n"
            "   - Grouping Form 57 by `crossing_id` flags repeat-incident corridor hotspots.\n"
            "3. Casualty Non-Double-Counting Rule:\n"
            "   - Form 57 records crossing-specific fatalities (`totkld`) and nonfatal injuries (`totinj`).\n"
            "   - In Report 1.12, crossing casualties are separated from non-crossing rail casualties\n"
            "     in Form 55a so total casualties are never double-counted.\n"
        )

    @mcp.resource("fra://reference/filter-glossary")
    def fra_filter_glossary() -> str:
        """FRA Report Filter Glossary (dnz7-ag8y) rules for Time, Geography, and Railroad Hierarchy."""
        return (
            "FRA Report Filter Glossary (dnz7-ag8y) — Website Filter Parity Rules:\n"
            "1. Timeframe Modes (`year_type`):\n"
            "   - `calendar`: Jan 1 – Dec 31 of the specified year.\n"
            "   - `fiscal`: Federal Fiscal Year Oct 1 (prior calendar year) – Sep 30 (target fiscal year).\n"
            "     Example: FY 2025 runs from October 1, 2024 through September 30, 2025.\n"
            "2. Railroad Hierarchy:\n"
            "   - `railroad_code`: Individual reporting carrier (e.g., UP, BNSF, NS, CSX, IC, GTW, WC).\n"
            "   - `parent_railroad_code`: Corporate parent/system rollup (e.g., `CN` aggregates Illinois\n"
            "     Central [IC], Grand Trunk Western [GTW], Wisconsin Central [WC], and DMIR).\n"
            "   - `railroad_class` / `railroad_group`: Class I freight, Class II regional, Class III\n"
            "     shortline, and Passenger/Commuter carriers (e.g., AMTK).\n"
            "3. Non-Cascading Fuzzy Geography:\n"
            "   - Unlike the FRA web UI where selecting a City requires pre-selecting State and County,\n"
            "     MCP queries support case-insensitive substring city matching (`UPPER(city) LIKE '%NAME%'`)\n"
            "     with optional state/county scoping, enabling cross-state metro comparisons.\n"
            "   - Also supports `fra_region` (Regions 1–8) and `smt` (Safety Management Team territory).\n"
        )

    @mcp.resource("fra://reference/cause-code-categories")
    def fra_cause_code_categories() -> str:
        """FRA Guide Appendix C major cause code groups for Form 54 rail equipment accidents."""
        return (
            "FRA Form 54 Appendix C — Major Train Accident Cause Code Groups:\n"
            "- T (T001–T999): Track, Roadbed, and Structures (geometry, rail/joint bar defects, frogs/switches)\n"
            "- H (H001–H999): Train Operation — Human Factors (brakes, switches lined improperly, speed, signals)\n"
            "- E (E001–E999): Mechanical and Electrical Failures (axles, bearings, wheels, couplers, trucks)\n"
            "- S (S001–S999): Signal and Communication (block signal failures, interlockings, PTC/cab signals)\n"
            "- M (M101–M599): Miscellaneous Causes (environmental, obstructions, lading, vandalism, grade crossing)\n"
        )