"""数据库性能监控 API — SHOW STATUS / pg_stat 实时采集"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from models.db_storage import DBStorage
from core.db_operations import DBOperations

router = APIRouter(prefix="/api/monitor", tags=["性能监控"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.get("/{conn_id}/status")
def get_server_status(
    conn_id: int,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取数据库服务器状态指标"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        metrics = {}

        if db_type == "MySQL":
            _, r, _, _ = ops.execute_sql(conn_data, "SHOW STATUS LIKE 'Uptime'")
            metrics["uptime"] = r[0][1] if r else "N/A"

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW STATUS LIKE 'Threads_connected'")
            metrics["threads_connected"] = int(r[0][1]) if r else 0

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW GLOBAL STATUS LIKE 'Queries'")
            metrics["total_queries"] = int(r[0][1]) if r else 0

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW GLOBAL STATUS LIKE 'Slow_queries'")
            metrics["slow_queries"] = int(r[0][1]) if r else 0

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW VARIABLES LIKE 'max_connections'")
            metrics["max_connections"] = int(r[0][1]) if r else 0

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW STATUS LIKE 'Open_tables'")
            metrics["open_tables"] = int(r[0][1]) if r else 0

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW STATUS LIKE 'Table_locks_immediate'")
            metrics["table_locks_immediate"] = int(r[0][1]) if r else 0

            _, r, _, _ = ops.execute_sql(conn_data, "SHOW STATUS LIKE 'Innodb_row_lock_current_waits'")
            metrics["innodb_lock_waits"] = int(r[0][1]) if r else 0

            metrics["connection_usage_pct"] = round(
                metrics["threads_connected"] / max(1, metrics["max_connections"]) * 100, 1
            )

            _, db_sizes, _, _ = ops.execute_sql(conn_data, """
                SELECT table_schema, ROUND(SUM(data_length + index_length) / 1024 / 1024, 2)
                FROM information_schema.tables
                GROUP BY table_schema ORDER BY 2 DESC LIMIT 10
            """)
            metrics["database_sizes"] = (
                [{"db": r[0], "size_mb": float(r[1])} for r in db_sizes] if db_sizes else []
            )

            _, processes, _, _ = ops.execute_sql(conn_data, "SHOW FULL PROCESSLIST")
            metrics["processes"] = []
            for r in (processes or [])[:20]:
                if len(r) >= 8:
                    metrics["processes"].append({
                        "id": r[0], "user": r[1], "host": r[2], "db": r[3],
                        "command": r[4], "time": r[5], "state": r[6],
                        "info": (r[7] or "")[:120],
                    })

            metrics["version"] = conn_data.get("version", "")

        elif db_type == "PostgreSQL":
            _, r, _, _ = ops.execute_sql(conn_data, "SELECT pg_postmaster_start_time()")
            metrics["uptime_raw"] = str(r[0][0]) if r else ""

            _, r, _, _ = ops.execute_sql(conn_data, "SELECT count(*) FROM pg_stat_activity")
            metrics["threads_connected"] = int(r[0][0]) if r else 0

            _, size_rows, _, _ = ops.execute_sql(conn_data, """
                SELECT datname, pg_database_size(datname) / 1048576.0
                FROM pg_database ORDER BY 2 DESC LIMIT 10
            """)
            metrics["database_sizes"] = (
                [{"db": r[0], "size_mb": round(float(r[1]), 2)} for r in size_rows] if size_rows else []
            )

            _, r, _, _ = ops.execute_sql(conn_data, "SELECT version()")
            metrics["version"] = r[0][0] if r else ""

        return {"success": True, "data": metrics}
    except Exception as e:
        return {"success": False, "message": str(e)}
