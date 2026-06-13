"""事件管理 API (MySQL Events)"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/events", tags=["事件管理"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


def _exec_select(ops, conn_data, sql, params=None, database=None):
    """执行 SELECT 查询，返回行列表"""
    _, rows, _, _, _ = ops.execute_sql(conn_data, sql, database=database, params=params)
    return rows


@router.get("/{conn_id}")
def list_events(
    conn_id: int,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """列出所有事件"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        db_name = database or conn_data.get("database", "")

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        if db_type == "MySQL":
            sql = """
                SELECT EVENT_NAME, EVENT_TYPE, EXECUTE_AT, INTERVAL_VALUE,
                       INTERVAL_FIELD, STARTS, ENDS, STATUS, ON_COMPLETION,
                       DEFINER, CREATED, LAST_ALTERED, EVENT_COMMENT
                FROM information_schema.EVENTS
                WHERE EVENT_SCHEMA = %s
                ORDER BY EVENT_NAME
            """
            rows = _exec_select(ops, conn_data, sql, (db_name,), database=db_name)
            events = []
            for row in rows:
                events.append({
                    "EVENT_NAME": row.get("EVENT_NAME", ""),
                    "EVENT_TYPE": row.get("EVENT_TYPE", ""),          # RECURRING / ONE TIME
                    "EXECUTE_AT": str(row.get("EXECUTE_AT", "") or ""),
                    "INTERVAL_VALUE": row.get("INTERVAL_VALUE", ""),
                    "INTERVAL_FIELD": row.get("INTERVAL_FIELD", ""),
                    "STARTS": str(row.get("STARTS", "") or ""),
                    "ENDS": str(row.get("ENDS", "") or ""),
                    "STATUS": row.get("STATUS", ""),                  # ENABLED / DISABLED / SLAVESIDE_DISABLED
                    "ON_COMPLETION": row.get("ON_COMPLETION", ""),    # PRESERVE / NOT PRESERVE
                    "DEFINER": row.get("DEFINER", ""),
                    "CREATED": str(row.get("CREATED", "") or ""),
                    "LAST_ALTERED": str(row.get("LAST_ALTERED", "") or ""),
                    "EVENT_COMMENT": row.get("EVENT_COMMENT", ""),
                })
            return {"success": True, "data": events}
        else:
            # PostgreSQL 没有 events，返回空
            return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{event_name}/ddl")
def get_event_ddl(
    conn_id: int,
    event_name: str,
    database: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取事件定义 DDL"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_name = database or conn_data.get("database", "")

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        sql = f"SHOW CREATE EVENT `{event_name}`"
        rows = _exec_select(ops, conn_data, sql, database=db_name)
        if rows:
            row = rows[0]
            ddl = row.get("Create Event", "")
            return {"success": True, "data": ddl}
        return {"success": False, "message": "事件不存在"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}")
def create_event(
    conn_id: int,
    body: dict,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """创建事件"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_name = body.get("database") or conn_data.get("database", "")
        event_sql = body.get("event_sql", "")

        if not event_sql:
            return {"success": False, "message": "事件 SQL 不能为空"}
        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        # 先确保事件调度器开启
        ops.execute_sql(conn_data, "SET GLOBAL event_scheduler = ON", database=db_name)
        ops.execute_sql(conn_data, event_sql, database=db_name)
        return {"success": True, "message": "事件创建成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/{conn_id}/{event_name}/toggle")
def toggle_event(
    conn_id: int,
    event_name: str,
    body: dict,
    database: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """启用/禁用事件"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_name = database or conn_data.get("database", "")
        enable = body.get("enable", True)

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        if enable:
            sql = f"ALTER EVENT `{event_name}` ENABLE"
        else:
            sql = f"ALTER EVENT `{event_name}` DISABLE"

        ops.execute_sql(conn_data, sql, database=db_name)
        status = "已启用" if enable else "已禁用"
        return {"success": True, "message": f"事件 {event_name} {status}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{event_name}")
def drop_event(
    conn_id: int,
    event_name: str,
    database: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除事件"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_name = database or conn_data.get("database", "")

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        sql = f"DROP EVENT IF EXISTS `{event_name}`"
        ops.execute_sql(conn_data, sql, database=db_name)
        return {"success": True, "message": f"事件 {event_name} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}
