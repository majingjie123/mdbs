"""触发器管理 API"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/triggers", tags=["触发器管理"])


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
def list_triggers(
    conn_id: int,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """列出所有触发器"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        db_name = database or conn_data.get("database", "")

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        if db_type == "MySQL":
            sql = """
                SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE,
                       ACTION_TIMING, ACTION_ORIENTATION, DEFINER, CREATED
                FROM information_schema.TRIGGERS
                WHERE TRIGGER_SCHEMA = %s
                ORDER BY TRIGGER_NAME
            """
            rows = _exec_select(ops, conn_data, sql, (db_name,), database=db_name)
            triggers = []
            for row in rows:
                triggers.append({
                    "TRIGGER_NAME": row.get("TRIGGER_NAME", ""),
                    "EVENT_MANIPULATION": row.get("EVENT_MANIPULATION", ""),
                    "EVENT_OBJECT_TABLE": row.get("EVENT_OBJECT_TABLE", ""),
                    "ACTION_TIMING": row.get("ACTION_TIMING", ""),
                    "ACTION_ORIENTATION": row.get("ACTION_ORIENTATION", ""),
                    "DEFINER": row.get("DEFINER", ""),
                    "CREATED": str(row.get("CREATED", "")),
                })
            return {"success": True, "data": triggers}
        else:
            # PostgreSQL
            schema_name = schema or "public"
            sql = """
                SELECT tgname AS TRIGGER_NAME,
                       c.relname AS EVENT_OBJECT_TABLE,
                       pg_catalog.pg_get_triggerdef(t.oid) AS TRIGGER_BODY
                FROM pg_catalog.pg_trigger t
                JOIN pg_catalog.pg_class c ON t.tgrelid = c.oid
                JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = %s
                  AND NOT t.tgisinternal
                ORDER BY tgname
            """
            rows = _exec_select(ops, conn_data, sql, (schema_name,), database=db_name)
            triggers = []
            for row in rows:
                triggers.append({
                    "TRIGGER_NAME": row.get("TRIGGER_NAME", ""),
                    "EVENT_OBJECT_TABLE": row.get("EVENT_OBJECT_TABLE", ""),
                    "TRIGGER_BODY": row.get("TRIGGER_BODY", ""),
                })
            return {"success": True, "data": triggers}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{trigger_name}/ddl")
def get_trigger_ddl(
    conn_id: int,
    trigger_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取触发器定义 DDL"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        db_name = database or conn_data.get("database", "")

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        if db_type == "MySQL":
            sql = f"SHOW CREATE TRIGGER `{trigger_name}`"
            rows = _exec_select(ops, conn_data, sql, database=db_name)
            if rows:
                row = rows[0]
                ddl = row.get("SQL Original Statement", row.get("Create Trigger", ""))
                return {"success": True, "data": ddl}
            return {"success": False, "message": "触发器不存在"}
        else:
            # PostgreSQL
            schema_name = schema or "public"
            sql = """
                SELECT pg_catalog.pg_get_triggerdef(t.oid) AS TRIGGER_BODY
                FROM pg_catalog.pg_trigger t
                JOIN pg_catalog.pg_class c ON t.tgrelid = c.oid
                JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = %s
                  AND tgname = %s
                  AND NOT t.tgisinternal
            """
            rows = _exec_select(ops, conn_data, sql, (schema_name, trigger_name), database=db_name)
            if rows:
                return {"success": True, "data": rows[0].get("TRIGGER_BODY", "")}
            return {"success": False, "message": "触发器不存在"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}")
def create_trigger(
    conn_id: int,
    body: dict,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """创建触发器"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_name = body.get("database") or conn_data.get("database", "")
        trigger_sql = body.get("trigger_sql", "")

        if not trigger_sql:
            return {"success": False, "message": "触发器 SQL 不能为空"}
        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        ops.execute_sql(conn_data, trigger_sql, database=db_name)
        return {"success": True, "message": "触发器创建成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{trigger_name}")
def drop_trigger(
    conn_id: int,
    trigger_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除触发器"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        db_name = database or conn_data.get("database", "")

        if not db_name:
            return {"success": False, "message": "未指定数据库"}

        if db_type == "MySQL":
            sql = f"DROP TRIGGER IF EXISTS `{trigger_name}`"
        else:
            sql = f'DROP TRIGGER IF EXISTS "{trigger_name}"'

        ops.execute_sql(conn_data, sql, database=db_name)
        return {"success": True, "message": f"触发器 {trigger_name} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}
