"""数据库级操作 API"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from ..schemas import CreateDBParams, MessageResponse
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/databases", tags=["数据库管理"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.get("/{conn_id}")
def list_databases(
    conn_id: int,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取数据库列表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        dbs = ops.get_databases(conn_data)
        return {"success": True, "data": dbs}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}")
def create_database(
    conn_id: int,
    params: CreateDBParams,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """创建数据库"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        ok, msg = ops.create_database(conn_data, params.model_dump())
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{db_name}")
def delete_database(
    conn_id: int,
    db_name: str,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除数据库"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        ok, msg = ops.delete_database(conn_data, db_name)
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/schemas")
def list_schemas(
    conn_id: int,
    database: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取模式列表 (PostgreSQL)"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        schemas = ops.get_schemas(conn_data, database=database or None)
        return {"success": True, "data": schemas}
    except Exception as e:
        return {"success": False, "message": str(e)}
