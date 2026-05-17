"""表结构查询 API"""

from fastapi import APIRouter, Depends
from dependencies import get_db_storage, get_db_ops
from schemas import MessageResponse
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/tables", tags=["表结构"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.get("/{conn_id}")
def list_tables(
    conn_id: int,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取表列表（含注释）"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        tables = ops.get_tables(conn_data, database=database or None, schema=schema or None)
        return {"success": True, "data": tables}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{table_name}/columns")
def get_table_columns(
    conn_id: int,
    table_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取表字段详情"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        cols = ops.get_table_columns_detailed(
            conn_data, table_name, database=database or None, schema=schema or None
        )
        return {"success": True, "data": cols}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{table_name}/indexes")
def get_table_indexes(
    conn_id: int,
    table_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取表索引"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        indexes = ops.get_table_indexes_detailed(
            conn_data, table_name, database=database or None, schema=schema or None
        )
        return {"success": True, "data": indexes}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{table_name}/ddl")
def get_table_ddl(
    conn_id: int,
    table_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取建表 DDL 语句"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        ddl = ops.get_table_ddl(conn_data, table_name, database=database or None, schema=schema or None)
        return {"success": True, "data": ddl}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{table_name}/primary-keys")
def get_primary_keys(
    conn_id: int,
    table_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取主键列表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        pks = ops.get_primary_keys(
            conn_data, table_name, database=database or None, schema=schema or None
        )
        return {"success": True, "data": pks}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/views")
def list_views(
    conn_id: int,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取视图列表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        views = ops.get_views(conn_data, database=database or None, schema=schema or None)
        return {"success": True, "data": views}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/relations")
def get_relations(
    conn_id: int,
    database: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取外键关联"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        rels = ops.get_relations(conn_data, database=database or None)
        return {"success": True, "data": rels}
    except Exception as e:
        return {"success": False, "message": str(e)}
