"""表结构查询 API"""

from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_db_storage, get_db_ops
from schemas import (
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
