from typing import Any, Dict, Optional
from fastmcp import FastMCP

from ..config import config
from ..db import DatabaseQueryError, execute_query


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def audit_delta_table_versions(
        dataset: str = "form_54",
        compare_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Inspects Unity Catalog Delta transaction history (`DESCRIBE HISTORY`) for any ingested
        FRA table ('form_54', 'form_55a', 'form_55', 'form_57') and optionally compares row
        counts against an earlier Delta `VERSION AS OF` snapshot to track retroactive FRA
        reporting updates under 49 CFR Part 225.
        """
        table_map = {
            "form_54": config.form_54_table,
            "form_55a": config.form_55a_table,
            "form_55": config.form_55_table,
            "form_57": config.form_57_table,
        }
        tbl = table_map.get(dataset.strip().lower())
        if not tbl:
            return {"error": f"Unknown dataset '{dataset}'. Choose from {list(table_map.keys())}."}

        fq = config.fq_table(tbl)
        try:
            history = execute_query(f"DESCRIBE HISTORY {fq} LIMIT 10")
            latest_count = execute_query(f"SELECT COUNT(*) AS row_count FROM {fq}")[0]["row_count"]

            comparison = None
            if compare_version is not None:
                v_int = int(compare_version)
                old_count = execute_query(
                    f"SELECT COUNT(*) AS row_count FROM {fq} VERSION AS OF {v_int}"
                )[0]["row_count"]
                comparison = {
                    "compared_version": v_int,
                    "historical_row_count": old_count,
                    "current_row_count": latest_count,
                    "net_row_delta": int(latest_count) - int(old_count),
                }

            return {
                "table": fq,
                "current_row_count": latest_count,
                "recent_delta_versions": [
                    {
                        "version": h.get("version"),
                        "timestamp": str(h.get("timestamp")),
                        "operation": h.get("operation"),
                    }
                    for h in history
                ],
                "version_comparison": comparison,
            }
        except DatabaseQueryError as err:
            return {"error": err.message, "hint": err.hint}