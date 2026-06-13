"""表结构查询 API"""

from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import get_db_storage, get_db_ops
from ..schemas import (
    MessageResponse,
    CreateTableParams,
    AlterColumnParams,
    DropColumnParams,
    RenameTableParams,
)
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


@router.get("/{conn_id}/functions")
def list_functions(
    conn_id: int,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取函数/存储过程列表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        funcs = ops.get_functions(conn_data, database=database or None, schema=schema or None)
        return {"success": True, "data": funcs}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/views/{view_name}/ddl")
def get_view_ddl(
    conn_id: int,
    view_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取视图 DDL 定义"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        ddl = ops.get_view_ddl(conn_data, view_name, database=database or None)
        return {"success": True, "data": ddl}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/functions/{func_name}/ddl")
def get_function_ddl(
    conn_id: int,
    func_name: str,
    func_type: str = "FUNCTION",
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取函数/存储过程 DDL 定义"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        ddl = ops.get_function_ddl(conn_data, func_name, func_type, database=database or None)
        return {"success": True, "data": ddl}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/functions/{func_name}/metadata")
def get_function_metadata(
    conn_id: int,
    func_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取函数/存储过程详细元数据"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        meta = ops.get_function_metadata(conn_data, func_name, database=database or None)
        return {"success": True, "data": meta}
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


# ═══════════════════════════════════════════════════════════
# 表结构修改（DDL）
# ═══════════════════════════════════════════════════════════


@router.post("/{conn_id}/create")
def create_table(
    conn_id: int,
    body: CreateTableParams,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """创建新表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")

        col_defs = []
        for col in body.columns:
            parts = [f"`{col.name}` {col.type}"]
            if col.auto_increment and db_type == "MySQL":
                parts.append("AUTO_INCREMENT")
            if not col.nullable:
                parts.append("NOT NULL")
            if col.default is not None:
                parts.append(f"DEFAULT {col.default}")
            if col.primary_key:
                parts.append("PRIMARY KEY")
            if col.comment and db_type == "MySQL":
                col_comment_esc = col.comment.replace("'", "''")
                parts.append(f"COMMENT '{col_comment_esc}'")
            col_defs.append(" ".join(parts))

        sql_parts = [f"CREATE TABLE `{body.table_name}` ("]
        sql_parts.append("  " + ",\n  ".join(col_defs))
        sql_parts.append(")")

        if db_type == "MySQL":
            sql_parts.append(f"ENGINE={body.engine}")
            sql_parts.append(f"DEFAULT CHARSET={body.charset}")
            if body.comment:
                comment_esc = body.comment.replace("'", "''")
                sql_parts.append(f"COMMENT='{comment_esc}'")

        sql = "\n".join(sql_parts)

        ops.execute_sql(conn_data, sql, database=body.database or None)
        return {"success": True, "message": f"表 {body.table_name} 创建成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{table_name}")
def drop_table(
    conn_id: int,
    table_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        sql = f"DROP TABLE IF EXISTS `{table_name}`"
        ops.execute_sql(conn_data, sql, database=database or None)
        return {"success": True, "message": f"表 {table_name} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/{conn_id}/{table_name}/rename")
def rename_table(
    conn_id: int,
    table_name: str,
    body: RenameTableParams,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """重命名表"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        sql = f"RENAME TABLE `{table_name}` TO `{body.new_name}`"
        ops.execute_sql(conn_data, sql, database=body.database or None)
        return {"success": True, "message": f"表已重命名为 {body.new_name}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/{table_name}/columns")
def add_column(
    conn_id: int,
    table_name: str,
    body: AlterColumnParams,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """添加列"""
    try:
        conn_data = _get_conn_data(conn_id, storage)

        parts = [f"ALTER TABLE `{table_name}` ADD COLUMN `{body.name}` {body.type}"]
        if not body.nullable:
            parts.append("NOT NULL")
        if body.default is not None:
            parts.append(f"DEFAULT {body.default}")
        if body.comment and conn_data.get("db_type", "MySQL") == "MySQL":
            cmt = body.comment.replace("'", "''")
            parts.append(f"COMMENT '{cmt}'")
        if body.first:
            parts.append("FIRST")
        elif body.after:
            parts.append(f"AFTER `{body.after}`")

        sql = " ".join(parts)
        ops.execute_sql(conn_data, sql, database=body.database or None)
        return {"success": True, "message": f"列 {body.name} 添加成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/{conn_id}/{table_name}/columns/{column_name}")
def modify_column(
    conn_id: int,
    table_name: str,
    column_name: str,
    body: AlterColumnParams,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """修改列定义"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")

        if db_type == "MySQL":
            parts = [f"ALTER TABLE `{table_name}` MODIFY COLUMN `{body.name}` {body.type}"]
        else:
            parts = [f'ALTER TABLE "{table_name}" ALTER COLUMN "{body.name}" TYPE {body.type}']

        if not body.nullable:
            if db_type == "MySQL":
                parts.append("NOT NULL")
            else:
                parts.append("SET NOT NULL")
        if body.default is not None and db_type == "MySQL":
            parts.append(f"DEFAULT {body.default}")
        if body.comment and db_type == "MySQL":
            cmt = body.comment.replace("'", "''")
            parts.append(f"COMMENT '{cmt}'")

        sql = " ".join(parts)
        ops.execute_sql(conn_data, sql, database=body.database or None)

        # PostgreSQL 用独立语句设置默认值和注释
        if db_type != "MySQL":
            if body.default is not None:
                sql_default = f'ALTER TABLE "{table_name}" ALTER COLUMN "{body.name}" SET DEFAULT {body.default}'
                ops.execute_sql(conn_data, sql_default, database=body.database or None)
            if body.comment:
                pg_cmt = body.comment.replace("'", "''")
                sql_comment = f"COMMENT ON COLUMN \"{table_name}\".\"{body.name}\" IS '{pg_cmt}'"
                ops.execute_sql(conn_data, sql_comment, database=body.database or None)

        return {"success": True, "message": f"列 {body.name} 修改成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{table_name}/columns/{column_name}")
def drop_column(
    conn_id: int,
    table_name: str,
    column_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除列"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        sql = f"ALTER TABLE `{table_name}` DROP COLUMN `{column_name}`"
        ops.execute_sql(conn_data, sql, database=database or None)
        return {"success": True, "message": f"列 {column_name} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════
# 外键管理
# ═══════════════════════════════════════════════════════════


@router.get("/{conn_id}/{table_name}/foreign-keys")
def get_foreign_keys(
    conn_id: int,
    table_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """获取表的所有外键"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        db = database or conn_data.get("database", "")

        if db_type == "MySQL":
            sql = """
                SELECT
                    kcu.CONSTRAINT_NAME,
                    kcu.COLUMN_NAME,
                    kcu.REFERENCED_TABLE_NAME,
                    kcu.REFERENCED_COLUMN_NAME,
                    rc.UPDATE_RULE,
                    rc.DELETE_RULE
                FROM information_schema.KEY_COLUMN_USAGE kcu
                JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
                    ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                    AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
                WHERE kcu.TABLE_SCHEMA = %s
                  AND kcu.TABLE_NAME = %s
                  AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            """
            result = ops.execute_sql(conn_data, sql, params=[db, table_name], database=db)
        elif db_type == "PostgreSQL":
            schema_name = schema or "public"
            sql = """
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_name AS referenced_table_name,
                    ccu.column_name AS referenced_column_name,
                    rc.update_rule,
                    rc.delete_rule
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                JOIN information_schema.referential_constraints rc
                    ON tc.constraint_name = rc.constraint_name
                    AND tc.table_schema = rc.constraint_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = %s
                  AND tc.table_schema = %s
            """
            result = ops.execute_sql(conn_data, sql, params=[table_name, schema_name], database=db)
        else:
            return {"success": False, "message": f"不支持的数据库类型: {db_type}"}

        if not result.get("success"):
            return {"success": False, "message": result.get("message", "查询失败")}

        rows = result.get("data", {}).get("rows", [])
        cols = result.get("data", {}).get("columns", [])
        fks = []
        for row in rows:
            item = {}
            for i, col in enumerate(cols):
                item[col.lower()] = row[i] if i < len(row) else None
            fks.append(item)
        return {"success": True, "data": fks}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/{table_name}/foreign-keys")
def add_foreign_key(
    conn_id: int,
    table_name: str,
    body: dict,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """添加外键约束"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")

        column_name = body.get("column_name", "")
        ref_table = body.get("ref_table", "")
        ref_column = body.get("ref_column", "id")
        constraint_name = body.get("constraint_name", f"fk_{table_name}_{column_name}")
        on_delete = body.get("on_delete", "RESTRICT")
        on_update = body.get("on_update", "RESTRICT")

        if not column_name or not ref_table:
            return {"success": False, "message": "缺少必要参数: column_name, ref_table"}

        if db_type == "MySQL":
            sql = (
                f"ALTER TABLE `{table_name}` "
                f"ADD CONSTRAINT `{constraint_name}` "
                f"FOREIGN KEY (`{column_name}`) "
                f"REFERENCES `{ref_table}` (`{ref_column}`) "
                f"ON DELETE {on_delete} ON UPDATE {on_update}"
            )
        elif db_type == "PostgreSQL":
            schema_name = schema or "public"
            sql = (
                f'ALTER TABLE "{schema_name}"."{table_name}" '
                f'ADD CONSTRAINT "{constraint_name}" '
                f'FOREIGN KEY ("{column_name}") '
                f'REFERENCES "{schema_name}"."{ref_table}" ("{ref_column}") '
                f"ON DELETE {on_delete} ON UPDATE {on_update}"
            )
        else:
            return {"success": False, "message": f"不支持的数据库类型: {db_type}"}

        ops.execute_sql(conn_data, sql, database=database or None)
        return {"success": True, "message": f"外键 {constraint_name} 已添加"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{table_name}/foreign-keys/{constraint_name}")
def drop_foreign_key(
    conn_id: int,
    table_name: str,
    constraint_name: str,
    database: str = "",
    schema: str = "",
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """删除外键约束"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")

        if db_type == "MySQL":
            sql = f"ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`"
        elif db_type == "PostgreSQL":
            schema_name = schema or "public"
            sql = f'ALTER TABLE "{schema_name}"."{table_name}" DROP CONSTRAINT "{constraint_name}"'
        else:
            return {"success": False, "message": f"不支持的数据库类型: {db_type}"}

        ops.execute_sql(conn_data, sql, database=database or None)
        return {"success": True, "message": f"外键 {constraint_name} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}
