from typing import Any, Dict, List, Optional, Sequence, Set
import databricks.sql
from databricks.sdk import WorkspaceClient

from .config import config

_COLUMN_CACHE: Dict[str, Set[str]] = {}


class DatabaseQueryError(RuntimeError):
    """Structured database error carrying an actionable hint for MCP tool responses."""

    def __init__(self, message: str, hint: str):
        super().__init__(message)
        self.message = message
        self.hint = hint


def _open_connection():
    """Opens a Databricks SQL Warehouse connection using ambient Notebook, App OAuth, or PAT auth."""
    config.validate()

    if config.databricks_host and config.databricks_token:
        hostname = config.databricks_host.replace("https://", "").rstrip("/")
        return databricks.sql.connect(
            server_hostname=hostname,
            http_path=config.http_path,
            access_token=config.databricks_token,
        )

    w = WorkspaceClient()
    hostname = (config.databricks_host or w.config.host or "").replace("https://", "").rstrip("/")

    if not hostname:
        raise DatabaseQueryError(
            "Databricks workspace hostname could not be resolved.",
            hint="Set DATABRICKS_HOST in app.yaml or environment variables.",
        )

    return databricks.sql.connect(
        server_hostname=hostname,
        http_path=config.http_path,
        credentials_provider=lambda: w.config.authenticate,
    )


def execute_query(
    query: str,
    parameters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Executes a parameterized SQL query and returns rows as a list of dicts."""
    try:
        with _open_connection() as conn:
            with conn.cursor() as cursor:
                if parameters:
                    cursor.execute(query, parameters)
                else:
                    cursor.execute(query)

                rows = cursor.fetchall()
                if not rows or not cursor.description:
                    return []

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    except DatabaseQueryError:
        raise
    except Exception as exc:
        err_msg = str(exc)
        hint = "Verify SQL Warehouse <DATABRICKS_WAREHOUSE_ID> is running and GRANT SELECT is applied to the app principal."
        if "PERMISSION_DENIED" in err_msg or "privileges" in err_msg.lower():
            hint = (
                "Run GRANT USE CATALOG ON CATALOG users, GRANT USE SCHEMA ON SCHEMA users.neeraj_koul, "
                "and GRANT SELECT ON TABLE ... TO `<app-service-principal>`."
            )
        elif "UNRESOLVED_COLUMN" in err_msg:
            hint = "A requested column name was not found in the Delta table schema. Check DESCRIBE TABLE output."
        raise DatabaseQueryError(f"SQL execution failed: {err_msg}", hint=hint) from exc


def get_table_columns(table_name: str, refresh: bool = False) -> Set[str]:
    """Returns lowercase column names for a Unity Catalog table (cached per process)."""
    fq = config.fq_table(table_name)
    if not refresh and fq in _COLUMN_CACHE:
        return _COLUMN_CACHE[fq]

    rows = execute_query(f"DESCRIBE TABLE {fq}")
    cols = {
        str(r["col_name"]).strip().lower()
        for r in rows
        if r.get("col_name") and not str(r["col_name"]).startswith("#")
    }
    _COLUMN_CACHE[fq] = cols
    return cols


def resolve_col(
    available_cols: Set[str],
    alias: str,
    candidates: Sequence[str],
    fallback_sql: Optional[str] = None,
) -> str:
    """
    Picks the first matching column name from candidates (exact or underscore-stripped
    for Socrata schemas like `countyname` / `typeofperson`) and prefixes with table alias.
    """
    normalized_map = {col.replace("_", ""): col for col in available_cols}

    for cand in candidates:
        c_lower = cand.lower()
        if c_lower in available_cols:
            return f"{alias}.`{c_lower}`"
        c_norm = c_lower.replace("_", "")
        if c_norm in normalized_map:
            return f"{alias}.`{normalized_map[c_norm]}`"

    if fallback_sql is not None:
        return fallback_sql
    raise DatabaseQueryError(
        f"None of candidate columns {list(candidates)} exist in table schema.",
        hint=f"Available columns include: {sorted(list(available_cols))[:25]}",
    )