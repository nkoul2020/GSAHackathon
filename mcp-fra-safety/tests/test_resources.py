import asyncio
import os
import sys

# Ensure src/ is importable when running directly in Databricks .py editor
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from fastmcp import Client, FastMCP
from fra_safety_mcp.resources import register_resources

EXPECTED_URIS = {
    "fra://reference/preparing-reports-guide",
    "fra://reports/1.12-methodology",
    "fra://reports/train-accidents-methodology",
    "fra://reports/form57-crossings-methodology",
    "fra://reference/filter-glossary",
    "fra://reference/cause-code-categories",
}


def _build_test_server() -> FastMCP:
    mcp = FastMCP("mcp-fra-safety-resource-test")
    register_resources(mcp)
    return mcp


async def _verify_all_resources() -> None:
    mcp = _build_test_server()

    # Connect via FastMCP in-memory transport (no network/App deployment needed)
    async with Client(mcp) as client:
        resources = await client.list_resources()
        registered_uris = {str(r.uri) for r in resources}

        missing = EXPECTED_URIS - registered_uris
        assert not missing, f"Missing expected resource URIs: {missing}"

        # Read every resource over MCP protocol and verify key 49 CFR Part 225 content
        guide = (await client.read_resource("fra://reference/preparing-reports-guide"))[0].text
        assert "49 CFR" in guide and "jointcd = '1'" in guide

        r112 = (await client.read_resource("fra://reports/1.12-methodology"))[0].text
        assert "1,000,000" in r112 and "200,000" in r112

        r203 = (await client.read_resource("fra://reports/train-accidents-methodology"))[0].text
        assert "Grand Total" in r203 and "jointcd = '2'" in r203

        r57 = (await client.read_resource("fra://reports/form57-crossings-methodology"))[0].text
        assert "crossing_id" in r57

        glossary = (await client.read_resource("fra://reference/filter-glossary"))[0].text
        assert "fiscal" in glossary.lower() and "parent_railroad_code" in glossary

        causes = (await client.read_resource("fra://reference/cause-code-categories"))[0].text
        for prefix in ("T001", "H001", "E001", "S001", "M101"):
            assert prefix in causes

        print(f"PASS: All {len(registered_uris)} FRA MCP resources registered and verified:")
        for uri in sorted(registered_uris):
            print(f"  - {uri}")


def test_resources_registered_and_readable() -> None:
    """Pytest / Databricks Tests-pane entrypoint."""
    asyncio.run(_verify_all_resources())


if __name__ == "__main__":
    test_resources_registered_and_readable()