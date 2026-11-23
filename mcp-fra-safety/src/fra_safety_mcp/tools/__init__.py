from fastmcp import FastMCP
from . import corridor_safety, cross_form_query, delta_audit, grade_crossings, joint_cause_audit, report_1_12, stb_employment, train_accidents

def register_tools(mcp: FastMCP) -> None:
    report_1_12.register(mcp)
    train_accidents.register(mcp)
    joint_cause_audit.register(mcp)
    grade_crossings.register(mcp)
    corridor_safety.register(mcp)
    delta_audit.register(mcp)
    cross_form_query.register(mcp)
    stb_employment.register(mcp)

register_all_tools = register_tools
