from contextlib import asynccontextmanager
from pathlib import Path
import sys

# Ensure `src/fra_safety_mcp` is importable regardless of working directory
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = str(REPO_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from fastapi import FastAPI
from fra_safety_mcp.config import config
from fra_safety_mcp.server import mcp

# Streamable-HTTP ASGI app at `/mcp` (avoids 307 trailing-slash redirects on POST /mcp)
mcp_app = mcp.http_app(path="/mcp")


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    config.validate()
    async with mcp_app.lifespan(app):
        yield


app = FastAPI(
    title="FRA & STB Rail Safety MCP Server",
    description="Governed MCP Server for 49 CFR Part 225 (FRA) and 49 CFR Part 1246 (STB) Rail Datasets",
    version="0.2.0",
    lifespan=app_lifespan,
)


@app.get("/")
def root() -> dict:
    return {
        "service": "mcp-fra-safety",
        "version": "0.2.0",
        "status": "running",
        "mcp_endpoint": "/mcp",
        "unity_catalog_target": f"{config.catalog}.{config.schema}",
        "warehouse_configured": bool(config.warehouse_id),
        "tables": {
            "form_54": config.form_54_table,
            "form_55a": config.form_55a_table,
            "form_55": config.form_55_table,
            "form_57": config.form_57_table,
            "stb_1246": config.stb_1246_table,
        },
        "capabilities": {
            "tools": 9,
            "resources": 6,
            "prompts": 4,
        },
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Mount FastMCP after health/root routes so `/mcp` handles all MCP JSON-RPC traffic
app.mount("/", mcp_app)
