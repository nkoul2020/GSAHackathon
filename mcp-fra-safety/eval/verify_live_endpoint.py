import asyncio
import concurrent.futures
import json
from pathlib import Path
import sys
import time
import urllib.request

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(REPO_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from databricks.sdk import WorkspaceClient
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fra_safety_mcp.config import config

APP_BASE_URL = config.app_url.rstrip("/")
if not APP_BASE_URL:
    raise RuntimeError("MCP_APP_URL is not set. Add MCP_APP_URL=https://<your-app>.aws.databricksapps.com to .env")
MCP_ENDPOINT = f"{APP_BASE_URL}/mcp"


def _wait_for_root(auth_headers: dict, timeout_sec: int = 45) -> None:
    deadline = time.time() + timeout_sec
    last_err = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{APP_BASE_URL}/", headers=auth_headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace").strip()
                if raw:
                    try:
                        print("Root Health (/):", json.dumps(json.loads(raw)))
                    except json.JSONDecodeError:
                        print(f"Root Health (/) HTTP {resp.status}: {raw[:200]}")
                else:
                    print(f"Root Health (/) HTTP {resp.status}: (empty body - app reachable)")
                return
        except Exception as exc:
            last_err = exc
            time.sleep(3)
    print(f"Warning: Root (/) check did not return within {timeout_sec}s ({last_err}); proceeding to /mcp...")


async def _check_live_app() -> None:
    w = WorkspaceClient()
    auth_headers = w.config.authenticate()

    _wait_for_root(auth_headers)

    transport = StreamableHttpTransport(url=MCP_ENDPOINT, headers=auth_headers)
    async with Client(transport) as client:
        tools = [t.name for t in await client.list_tools()]
        resources = [str(r.uri) for r in await client.list_resources()]
        prompts = [p.name for p in await client.list_prompts()]
        print(f"Live /mcp Primitives -> Tools ({len(tools)}): {tools}")
        print(f"Live /mcp Resources ({len(resources)}), Prompts ({len(prompts)})")

        res = await client.call_tool(
            "analyze_class1_employment_and_safety",
            {"start_year": 2020, "end_year": 2025, "railroad_code": "CSXT"},
        )
        assert "error" not in res.data, f"Live app SQL error (check GRANTs): {res.data}"
        print("Live /mcp STB 1246 + FRA Query: PASS")
        print("Sample Live Result:", json.dumps(res.data["cross_form_fra_safety_rates"], indent=2))


def verify_live() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, _check_live_app()).result()


if __name__ == "__main__":
    verify_live()
