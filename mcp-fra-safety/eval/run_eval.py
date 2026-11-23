import asyncio
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(REPO_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from fastmcp import Client
from fra_safety_mcp.server import mcp

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def _get_nested(payload: Dict[str, Any], dotted_path: str) -> Any:
    cur: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return "__MISSING__"
        cur = cur[part]
    return cur


def _validate_case(case: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return [f"Expected dict response, got {type(data).__name__}"]
    if "error" in data:
        return [f"Tool returned error: {data.get('error')} (hint: {data.get('hint', '')})"]

    checks = case.get("checks", {})

    for key in checks.get("required_keys", []):
        if key not in data:
            errors.append(f"Missing required key '{key}'")

    for path in checks.get("not_null_paths", []):
        val = _get_nested(data, path)
        if val in ("__MISSING__", None):
            errors.append(f"Expected '{path}' to be non-null, got {val}")

    for path in checks.get("null_paths", []):
        val = _get_nested(data, path)
        if val is not None:
            errors.append(f"Expected '{path}' to be None (FRA geographic blank rule), got {val}")

    for path, expected in checks.get("equals", {}).items():
        val = _get_nested(data, path)
        if val != expected:
            errors.append(f"Expected '{path}' == {expected!r}, got {val!r}")

    for path, substr in checks.get("contains_text", {}).items():
        val = str(_get_nested(data, path))
        if substr not in val:
            errors.append(f"Expected '{substr}' inside '{path}', got {val!r}")

    for path in checks.get("non_empty_list", []):
        val = _get_nested(data, path)
        if not isinstance(val, list) or len(val) == 0:
            errors.append(f"Expected non-empty list at '{path}', got {type(val).__name__}")

    if checks.get("table2_overlap_check"):
        breakdown = data.get("breakdown", [])
        gt = data.get("grand_total", {}).get("deduplicated_grand_total_accidents", 0)
        row_sum = sum(int(r.get("accident_count", 0)) for r in breakdown)
        if row_sum < int(gt):
            errors.append(
                f"Table 2 railroad sum ({row_sum}) should be >= deduplicated grand total ({gt})"
            )

    return errors


async def _execute_eval_async() -> Dict[str, Any]:
    cases = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    case_results: List[Dict[str, Any]] = []
    start_all = time.perf_counter()

    async with Client(mcp) as client:
        # 1. Verify all 6 Resources return substantive 49 CFR Part 225 guidance
        resources = await client.list_resources()
        resource_checks = []
        for res in resources:
            uri = str(res.uri)
            content = await client.read_resource(uri)
            text_len = sum(len(getattr(item, "text", "")) for item in content)
            resource_checks.append({"uri": uri, "bytes": text_len, "passed": text_len > 100})

        # 2. Verify all 4 Prompts render cleanly with test arguments
        prompt_args_map = {
            "metro_safety_audit_briefing": {"city": "Chicago", "state": "IL"},
            "railroad_system_safety_scorecard": {"parent_railroad_code": "CN"},
            "grade_crossing_hotspot_audit": {"state": "TX"},
            "joint_track_discrepancy_review": {"state": "IL"},
        }
        prompts = await client.list_prompts()
        prompt_checks = []
        for prm in prompts:
            p_res = await client.get_prompt(prm.name, prompt_args_map.get(prm.name, {}))
            msg_count = len(p_res.messages)
            prompt_checks.append({"name": prm.name, "messages": msg_count, "passed": msg_count >= 1})

        # 3. Execute all 12 Tool benchmark cases
        for case in cases:
            t0 = time.perf_counter()
            raw_res = await client.call_tool(case["tool"], case["args"])
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            data = raw_res.data if isinstance(raw_res.data, dict) else {}
            failures = _validate_case(case, data)
            passed = len(failures) == 0

            case_results.append({
                "id": case["id"],
                "category": case["category"],
                "tool": case["tool"],
                "latency_ms": elapsed_ms,
                "passed": passed,
                "failures": failures,
            })
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {case['id']} ({elapsed_ms} ms)")
            if failures:
                for f in failures:
                    print(f"       -> {f}")

    total_elapsed_s = round(time.perf_counter() - start_all, 2)
    passed_cases = sum(1 for r in case_results if r["passed"])
    passed_resources = sum(1 for r in resource_checks if r["passed"])
    passed_prompts = sum(1 for r in prompt_checks if r["passed"])

    summary = {
        "server": "mcp-fra-safety",
        "total_duration_s": total_elapsed_s,
        "tool_cases_passed": passed_cases,
        "tool_cases_total": len(case_results),
        "tool_pass_rate_pct": round((passed_cases / max(1, len(case_results))) * 100, 1),
        "avg_tool_latency_ms": round(
            sum(r["latency_ms"] for r in case_results) / max(1, len(case_results)), 1
        ),
        "resources_passed": passed_resources,
        "resources_total": len(resource_checks),
        "prompts_passed": passed_prompts,
        "prompts_total": len(prompt_checks),
        "resource_details": resource_checks,
        "prompt_details": prompt_checks,
        "case_results": case_results,
    }

    try:
        RESULTS_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        Path("/tmp/mcp_fra_safety_eval_results.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

    return summary


def run_benchmark() -> Dict[str, Any]:
    """Notebook-safe and CLI-safe entrypoint for running the full MCP evaluation suite."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _execute_eval_async()).result()


if __name__ == "__main__":
    report = run_benchmark()
    print(
        f"\nBenchmark Complete: {report['tool_cases_passed']}/{report['tool_cases_total']} tool cases "
        f"({report['tool_pass_rate_pct']}%), {report['resources_passed']}/{report['resources_total']} resources, "
        f"{report['prompts_passed']}/{report['prompts_total']} prompts in {report['total_duration_s']}s."
    )
    if report["tool_cases_passed"] < report["tool_cases_total"]:
        sys.exit(1)