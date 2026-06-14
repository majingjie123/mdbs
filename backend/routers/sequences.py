"""序列管理 API (PostgreSQL)"""

from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/sequences", tags=["序列管理"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.get("/{conn_id}")
def list_sequences(
    conn_id: int,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """列出所有序列 (PostgreSQL)"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "PostgreSQL")
        if db_type != "PostgreSQL":
            return {"success": False, "message": "序列管理仅支持 PostgreSQL"}

        sc = schema or "public"
        sql = """
            SELECT
                c.relname AS sequence_name,
                n.nspname AS schema_name,
                pg_catalog.pg_get_userbyid(c.relowner) AS owner,
                c.reltuples::bigint AS cache_size,
                s.seqstart AS start_value,
                s.seqincrement AS increment,
                s.seqmax AS max_value,
                s.seqmin AS min_value,
                s.seqcache AS cache_value,
                s.seqcycle AS cycle
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
            LEFT JOIN pg_catalog.pg_sequence s ON c.oid = s.seqrelid
            WHERE c.relkind = 'S'
              AND n.nspname = %s
            ORDER BY c.relname
        """
        params = [sc]
        _, rows, _, _, _ = ops.execute_sql(conn_data, sql, database=database or None, params=params)
        result = []
        for r in (rows or []):
            result.append({
                "sequence_name": r[0],
                "schema_name": r[1],
                "owner": r[2],
                "cache_size": r[3],
                "start_value": r[4],
                "increment": r[5],
                "max_value": r[6],
                "min_value": r[7],
                "cache_value": r[8],
                "cycle": bool(r[9]) if r[9] is not None else False,
            })
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{seq_name}/ddl")
def get_sequence_ddl(
    conn_id: int,
    seq_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取序列定义 DDL"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "PostgreSQL")
        if db_type != "PostgreSQL":
            return {"success": False, "message": "序列管理仅支持 PostgreSQL"}

        sc = schema or "public"
        sql = f"SELECT pg_catalog.pg_get_serial_sequence('{sc}.{seq_name}', '')"
        _, rows, _, _, _ = ops.execute_sql(conn_data, sql, database=database or None)
        ddl_sql = f"SELECT pg_catalog.pg_get_serial_sequence('{sc}.{seq_name}', '')"
        # 直接使用 pg_get_serial_sequence 或查询 pg_sequence 元数据
        ddl_sql = f"""
            SELECT 'CREATE SEQUENCE {sc}.{seq_name}'
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = '{seq_name}' AND n.nspname = '{sc}' AND c.relkind = 'S'
        """
        _, rows, _, _, _ = ops.execute_sql(conn_data, ddl_sql, database=database or None)
        if rows and len(rows) > 0:
            ddl = rows[0][0] if rows[0] else f"-- Sequence: {seq_name}"
        else:
            ddl = f"-- Sequence not found: {seq_name}"
        return {"success": True, "data": ddl}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}")
def create_sequence(
    conn_id: int,
    body: dict,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """创建序列"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "PostgreSQL")
        if db_type != "PostgreSQL":
            return {"success": False, "message": "序列管理仅支持 PostgreSQL"}

        seq_name = body.get("sequence_name", "")
        if not seq_name:
            return {"success": False, "message": "序列名称不能为空"}

        sc = schema or "public"
        start_val = body.get("start_value", 1)
        increment = body.get("increment", 1)
        min_val = body.get("min_value", 1)
        max_val = body.get("max_value", 9223372036854775807)
        cache_val = body.get("cache_value", 1)
        cycle = body.get("cycle", False)

        sql = f"""CREATE SEQUENCE {sc}.{seq_name}
            START WITH {start_val}
            INCREMENT BY {increment}
            MINVALUE {min_val}
            MAXVALUE {max_val}
            CACHE {cache_val}
            {'CYCLE' if cycle else 'NO CYCLE'}
        """
        ops.execute_sql(conn_data, sql, database=database or None)
        return {"success": True, "message": f"序列 {seq_name} 创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{seq_name}")
def drop_sequence(
    conn_id: int,
    seq_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除序列"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "PostgreSQL")
        if db_type != "PostgreSQL":
            return {"success": False, "message": "序列管理仅支持 PostgreSQL"}

        sc = schema or "public"
        sql = f"DROP SEQUENCE IF EXISTS {sc}.{seq_name}"
        ops.execute_sql(conn_data, sql, database=database or None)
        return {"success": True, "message": f"序列 {seq_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}
