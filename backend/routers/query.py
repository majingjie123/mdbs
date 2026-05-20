"""SQL 查询执行 API"""

import threading
from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from ..schemas import ExecuteSQLRequest, BatchSQLRequest, MessageResponse
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/query", tags=["SQL 执行"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.post("/execute")
def execute_sql(
    req: ExecuteSQLRequest,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """执行单条 SQL 语句"""
    cancel = threading.Event()
    try:
        conn_data = _get_conn_data(req.conn_id, storage)
        schema = req.schema_name if conn_data.get("db_type") == "PostgreSQL" else None
        cols, rows, affected, is_query, truncated, total = ops.execute_sql(
            conn_data,
            req.sql,
            database=req.database,
            params=req.params,
            schema=schema,
            cancel_event=cancel,
            limit=req.limit,
            offset=req.offset,
        )
        return {
            "success": True,
            "data": {
                "columns": cols,
                "rows": rows,
                "affected": affected,
                "is_query": is_query,
                "truncated": truncated,
                "total": total,
            },
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/batch")
def execute_batch_sql(
    req: BatchSQLRequest,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """批量执行 SQL"""
    try:
        conn_data = _get_conn_data(req.conn_id, storage)
        sql_list = [(s.sql, s.params) for s in req.sqls]
        schema = req.schema_name if conn_data.get("db_type") == "PostgreSQL" else None
        ok, msg = ops.execute_batch_sql(
            conn_data, sql_list, database=req.database, schema=schema
        )
        return {"success": ok, "message": str(msg)}
    except Exception as e:
        return {"success": False, "message": str(e)}
