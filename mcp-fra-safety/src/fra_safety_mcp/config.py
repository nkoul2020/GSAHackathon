import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    candidates = [Path(__file__).resolve().parents[2] / ".env", Path.cwd() / ".env"]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and val:
                os.environ.setdefault(key, val)
        break


_load_dotenv()


@dataclass(frozen=True)
class ServerConfig:
    databricks_host: str = os.getenv("DATABRICKS_HOST", "")
    databricks_token: str = os.getenv("DATABRICKS_TOKEN", "")
    warehouse_id: str = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
    catalog: str = os.getenv("FRA_CATALOG", "main")
    schema: str = os.getenv("FRA_SCHEMA", "fra_safety")
    app_url: str = os.getenv("MCP_APP_URL", "")
    form_54_table: str = os.getenv("FRA_FORM_54_TABLE", "form_54_accidents")
    form_55a_table: str = os.getenv("FRA_FORM_55A_TABLE", "form_55a_casualties")
    form_55_table: str = os.getenv("FRA_FORM_55_TABLE", "form_55_operational")
    form_57_table: str = os.getenv("FRA_FORM_57_TABLE", "form_57_crossings")
    stb_1246_table: str = os.getenv("FRA_STB_1246_TABLE", "stb_1246_all_carriers")

    @property
    def http_path(self) -> str:
        return f"/sql/1.0/warehouses/{self.warehouse_id}" if self.warehouse_id else ""

    def validate(self) -> None:
        if not self.warehouse_id:
            raise ValueError("DATABRICKS_WAREHOUSE_ID is not set in .env or app.yaml.")
        if not self.catalog or not self.schema:
            raise ValueError("FRA_CATALOG and FRA_SCHEMA must both be configured.")

    def fq_table(self, table_name: str) -> str:
        return f"`{self.catalog}`.`{self.schema}`.`{table_name}`"


config = ServerConfig()
