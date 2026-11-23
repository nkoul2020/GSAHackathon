from fastmcp import FastMCP

from .prompts import register_prompts
from .resources import register_resources
from .tools import register_tools

mcp = FastMCP(
    name="mcp-fra-safety",
    instructions=(
        "Official Federal Railroad Administration (FRA) Safety Dataset Access MCP Server. "
        "Before interpreting counts or rates, consult the `fra://reference/preparing-reports-guide` "
        "and `fra://reports/1.12-methodology` resources to enforce 49 CFR Part 225 deduplication "
        "(`incidentkey` + `jointcd = '1'`), crossing exclusion rules, and Form 55 rate formulas."
    ),
)

register_resources(mcp)
register_tools(mcp)
register_prompts(mcp)