"""慢查询日志 API — MySQL 慢查询查询/设置/分析"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/slow-queries", tags=["慢查询日志"])
import json


@router.get("/{conn_id}/settings")
def get_slow_query_settings(
    conn_id: int,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """获取慢查询配置"""
    try:
        conn_data = storage.get_connection(conn_id)
        if not conn_data:
            return {"success": False, "message": "连接不存在"}
        db_type = conn_data.get("db_type", "MySQL")
        settings = {}

        if db_type == "MySQL":
            vars_to_check = [
                "slow_query_log", "slow_query_log_file", "long_query_time",
                "log_queries_not_using_indexes", "min_examined_row_limit",
                "log_slow_admin_statements", "log_throttle_queries_not_using_indexes",
            ]
            for var in vars_to_check:
                try:
                    _, rows, _, _, _ = ops.execute_sql(
                        conn_data, f"SHOW VARIABLES LIKE '{var}'"
                    )
                    if rows:
                        settings[var] = rows[0].get("Value", "") if isinstance(rows[0], dict) else rows[0][1] if len(rows[0]) > 1 else ""
                except Exception:
                    pass
        elif db_type == "PostgreSQL":
            # pg 慢查询设置
            vars_to_check = ["log_min_duration_statement", "shared_buffers", "work_mem"]
            for var in vars_to_check:
                try:
                    _, rows, _, _, _ = ops.execute_sql(
                        conn_data, f"SHOW {var}"
                    )
                    if rows:
                        settings[var] = list(rows[0].values())[0] if isinstance(rows[0], dict) else rows[0][0]
                except Exception:
                    pass

        return {"success": True, "data": settings}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/top")
def get_top_slow_queries(
    conn_id: int,
    limit: int = 20,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """获取 TOP 慢查询（从 performance_schema 或 mysql.slow_log）"""
    try:
        conn_data = storage.get_connection(conn_id)
        if not conn_data:
            return {"success": False, "message": "连接不存在"}
        db_type = conn_data.get("db_type", "MySQL")

        queries = []
        source = ""

        if db_type == "MySQL":
            # 尝试从 performance_schema.events_statements_summary_by_digest 读取
            try:
                sql = """
                    SELECT
                        DIGEST_TEXT AS query,
                        SCHEMA_NAME AS db,
                        COUNT_STAR AS exec_count,
                        ROUND(SUM_TIMER_WAIT / 1000000000000, 3) AS total_sec,
                        ROUND(AVG_TIMER_WAIT / 1000000000000, 4) AS avg_sec,
                        ROUND(MAX_TIMER_WAIT / 1000000000000, 3) AS max_sec,
                        ROUND(SUM_ROWS_EXAMINED / GREATEST(COUNT_STAR, 1), 1) AS avg_rows_examined,
                        SUM_ROWS_SENT AS rows_sent,
                        FIRST_SEEN, LAST_SEEN
                    FROM performance_schema.events_statements_summary_by_digest
                    WHERE DIGEST_TEXT IS NOT NULL
                    ORDER BY SUM_TIMER_WAIT DESC
                    LIMIT {}
                """.format(limit)
                _, rows, _, _, _ = ops.execute_sql(conn_data, sql)
                if rows:
                    source = "performance_schema.events_statements_summary_by_digest"
                    queries = rows
            except Exception:
                pass

            # 如果 performance_schema 不可用，尝试 mysql.slow_log 表
            if not queries:
                try:
                    _, rows, _, _, _ = ops.execute_sql(
                        conn_data, f"""
                            SELECT
                                sql_text AS query,
                                db,
                                query_time,
                                lock_time,
                                rows_examined,
                                rows_sent,
                                thread_id
                            FROM mysql.slow_log
                            ORDER BY start_time DESC
                            LIMIT {limit}
                        """
                    )
                    if rows:
                        source = "mysql.slow_log"
                        queries = rows
                except Exception:
                    pass

        elif db_type == "PostgreSQL":
            try:
                _, rows, _, _, _ = ops.execute_sql(
                    conn_data, f"""
                        SELECT
                            query,
                            calls,
                            ROUND(total_exec_time / 1000, 2) AS total_ms,
                            ROUND(mean_exec_time, 2) AS avg_ms,
                            ROUND(max_exec_time, 2) AS max_ms,
                            ROUND(min_exec_time, 2) AS min_ms,
                            rows,
                            shared_blks_hit,
                            shared_blks_read
                        FROM pg_stat_statements
                        ORDER BY total_exec_time DESC
                        LIMIT {limit}
                    """
                )
                if rows:
                    source = "pg_stat_statements"
                    queries = rows
            except Exception:
                pass

        return {"success": True, "data": {"source": source, "queries": queries}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/toggle-slow-log")
def toggle_slow_log(
    conn_id: int,
    body: dict,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """开启/关闭慢查询日志（需 SUPER 权限）"""
    try:
        conn_data = storage.get_connection(conn_id)
        if not conn_data:
            return {"success": False, "message": "连接不存在"}
        enable = body.get("enable", True)
        long_query_time = body.get("long_query_time", 2)

        ops.execute_sql(conn_data, f"SET GLOBAL slow_query_log = {'ON' if enable else 'OFF'}")
        if enable and long_query_time:
            ops.execute_sql(conn_data, f"SET GLOBAL long_query_time = {long_query_time}")

        return {"success": True, "message": f"慢查询日志已{'开启' if enable else '关闭'}"}
    except Exception as e:
        return {"success": False, "message": f"操作失败: {str(e)}"}
