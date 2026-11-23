# neeraj 
import asyncio
import concurrent.futures
import os
import sys

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from fastmcp import Client
from fra_safety_mcp.server import mcp

EXPECTED_TOOLS = {
    "get_report_1_12_rail_safety_overview",
    "get_train_accident_summary",
    "audit_joint_track_cause_discrepancies",
    "analyze_highway_rail_crossings",
    "analyze_metro_corridor_safety",
    "audit_delta_table_versions",
}

EXPECTED_RESOURCES = {
    "fra://reference/preparing-reports-guide",
    "fra://reports/1.12-methodology",
    "fra://reports/train-accidents-methodology",
    "fra://reports/form57-crossings-methodology",
    "fra://reference/filter-glossary",
    "fra://reference/cause-code-categories",
}

EXPECTED_PROMPTS = {
    "metro_safety_audit_briefing",
    "railroad_system_safety_scorecard",
    "grade_crossing_hotspot_audit",
    "joint_track_discrepancy_review",
}


def _run_in_worker_loop(coro):
    """Runs an async coroutine in a clean worker thread event loop."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _run_full_server_check() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
        resources = {str(r.uri) for r in await client.list_resources()}
        prompts = {p.name for p in await client.list_prompts()}

        assert EXPECTED_TOOLS.issubset(tools), f"Missing tools: {EXPECTED_TOOLS - tools}"
        assert EXPECTED_RESOURCES.issubset(resources), f"Missing resources: {EXPECTED_RESOURCES - resources}"
        assert EXPECTED_PROMPTS.issubset(prompts), f"Missing prompts: {EXPECTED_PROMPTS - prompts}"

        # Verify live Report 1.12 query (Parent Railroad = CN)
        r112 = await client.call_tool(
            "get_report_1_12_rail_safety_overview",
            {"start_year": 2023, "end_year": 2024, "parent_railroad_code": "CN"},
        )
        assert "error" not in r112.data, f"Report 1.12 failed: {r112.data}"
        assert r112.data["operational_and_rates_form55"]["total_train_miles"] is not None

        # Verify FRA portal geographic blank-rate rule on Report 1.12
        r112_geo = await client.call_tool(
            "get_report_1_12_rail_safety_overview",
            {"start_year": 2023, "end_year": 2024, "state": "IL"},
        )
        assert "error" not in r112_geo.data, f"Report 1.12 geo failed: {r112_geo.data}"
        assert r112_geo.data["operational_and_rates_form55"]["total_train_miles"] is None

        print("PASS: All 6 tools, 6 resources, and 4 prompts verified against Unity Catalog.")


def test_mcp_server_end_to_end() -> None:
    """Pytest / Databricks Tests-pane entrypoint."""
    _run_in_worker_loop(_run_full_server_check())


if __name__ == "__main__":
    test_mcp_server_end_to_end()