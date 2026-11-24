import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple

from fastmcp import Client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import fra_safety_mcp.server as server_mod  # noqa: E402


def _resolve_server() -> Any:
    if hasattr(server_mod, "create_server"):
        return server_mod.create_server()
    if hasattr(server_mod, "mcp"):
        return server_mod.mcp
    raise RuntimeError("Could not find `create_server` or `mcp` in `fra_safety_mcp.server`.")


def _extract_tool_payload(call_result: Any) -> Dict[str, Any]:
    """Normalizes FastMCP CallToolResult objects across FastMCP versions."""
    if isinstance(call_result, dict):
        return call_result
    data = getattr(call_result, "data", None)
    if isinstance(data, dict):
        return data
    content = getattr(call_result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"raw_text": text}
    return {}


def _get_by_path(data: Any, dotted_path: str) -> Tuple[bool, Any]:
    """Traverses a dot-separated key path (e.g. 'grand_total.deduplicated_grand_total_accidents')."""
    curr = data
    for part in dotted_path.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
            curr = curr[int(part)]
        else:
            return False, None
    return True, curr


def _evaluate_checks(payload: Dict[str, Any], checks: Dict[str, Any]) -> List[str]:
    """Validates a tool response payload against declarative assertions in dataset.jsonl."""
    failures: List[str] = []
    required_keys: List[str] = checks.get("required_keys", [])

    # Treat top-level tool errors as failures unless the test explicitly expects an "error" key
    if isinstance(payload, dict) and "error" in payload and "error" not in required_keys:
        hint = payload.get("hint", "")
        hint_suffix = f" (hint: {hint})" if hint else ""
        return [f"Tool returned error: {payload['error']}{hint_suffix}"]

    for key in required_keys:
        if key not in payload:
            failures.append(f"Missing required key: '{key}'")

    for path in checks.get("not_null_paths", []):
        exists, val = _get_by_path(payload, path)
        if not exists or val is None:
            failures.append(f"Expected non-null value at '{path}', got {val!r}")

    for path in checks.get("null_paths", []):
        exists, val = _get_by_path(payload, path)
        if not exists or val is not None:
            failures.append(f"Expected None/null at '{path}', got {val!r}")

    for path, expected in checks.get("equals", {}).items():
        exists, actual = _get_by_path(payload, path)
        if not exists or actual != expected:
            failures.append(f"Mismatch at '{path}': expected {expected!r}, got {actual!r}")

    for path, expected_sub in checks.get("contains_text", {}).items():
        exists, actual = _get_by_path(payload, path)
        if not exists or str(expected_sub) not in str(actual):
            failures.append(
                f"Expected substring {expected_sub!r} at '{path}', got {actual!r}"
            )

    for path in checks.get("non_empty_list", []):
        exists, val = _get_by_path(payload, path)
        if not exists or not isinstance(val, list) or len(val) == 0:
            failures.append(f"Expected non-empty list at '{path}', got {type(val).__name__} (len={len(val) if isinstance(val, list) else 'N/A'})")

    if checks.get("table2_overlap_check"):
        breakdown = payload.get("breakdown", [])
        grand_total = payload.get("grand_total", {})
        dedup_total = int(grand_total.get("deduplicated_grand_total_accidents", 0) or 0)
        carrier_sum = sum(int(row.get("accident_count", 0) or 0) for row in breakdown)
        if carrier_sum <= dedup_total:
            failures.append(
                f"Table 2 overlap check failed: sum of carrier involvements ({carrier_sum}) "
                f"must exceed deduplicated grand total ({dedup_total})"
            )

    return failures


async def _execute_eval_async() -> Dict[str, Any]:
    dataset_path = Path(__file__).resolve().parent / "dataset.jsonl"
    cases = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    prompt_args_map: Dict[str, Dict[str, Any]] = {
        "metro_safety_audit_briefing": {"city": "Chicago", "state": "IL"},
        "railroad_system_safety_scorecard": {"parent_railroad_code": "BNSF"},
        "railroad_workforce_and_safety_briefing": {"parent_railroad_code": "BNSF"},
        "grade_crossing_hotspot_audit": {"state": "TX"},
        "joint_track_discrepancy_review": {"state": "IL"},
    }

    mcp_server = _resolve_server()
    results: List[Dict[str, Any]] = []

    async with Client(mcp_server) as client:
        # 1. Verify MCP Resources
        resources = await client.list_resources()
        for res in resources:
            await client.read_resource(res.uri)
        print(f"Verified {len(resources)} MCP resources.")

        # 2. Verify MCP Prompts
        prompts = await client.list_prompts()
        for prm in prompts:
            p_res = await client.get_prompt(prm.name, prompt_args_map.get(prm.name, {}))
            if not getattr(p_res, "messages", None):
                raise AssertionError(f"Prompt '{prm.name}' rendered empty messages.")
        print(f"Verified {len(prompts)} MCP prompts.\n")

        # 3. Execute Benchmark Tool Cases
        for case in cases:
            case_id = case["id"]
            tool_name = case["tool"]
            args = case.get("args", {})
            checks = case.get("checks", {})

            t0 = time.perf_counter()
            raw_res = await client.call_tool(tool_name, args)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

            payload = _extract_tool_payload(raw_res)
            failures = _evaluate_checks(payload, checks)
            passed = len(failures) == 0

            if passed:
                print(f"[PASS] {case_id} ({elapsed_ms} ms)")
            else:
                print(f"[FAIL] {case_id} ({elapsed_ms} ms)")
                for msg in failures:
                    print(f"       -> {msg}")

            results.append({
                "id": case_id,
                "category": case.get("category", ""),
                "tool": tool_name,
                "passed": passed,
                "elapsed_ms": elapsed_ms,
                "failures": failures,
            })

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"\nEvaluation Summary: {passed_count}/{total_count} passed.")

    report = {
        "passed": passed_count,
        "total": total_count,
        "all_passed": passed_count == total_count,
        "results": results,
    }
    report_path = Path(__file__).resolve().parent / "eval_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if passed_count != total_count:
        raise SystemExit(1)

    return report


def run_benchmark() -> Dict[str, Any]:
    """Runs the async eval suite in a dedicated thread so it works inside Databricks notebooks."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _execute_eval_async()).result()


if __name__ == "__main__":
    run_benchmark()