"""用户权限管理 API (MySQL users & privileges)"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/users", tags=["用户权限管理"])


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


def _exec_select(ops, conn_data, sql, params=None, database=None):
    _, rows, _, _, _ = ops.execute_sql(conn_data, sql, database=database, params=params)
    return rows


@router.get("/{conn_id}")
def list_users(
    conn_id: int,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """列出 MySQL 用户和权限摘要"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")

        users = []
        if db_type == "MySQL":
            # 1. 查询用户列表
            rows = _exec_select(ops, conn_data,
                "SELECT User, Host, account_locked, password_expired "
                "FROM mysql.user ORDER BY User")
            for row in rows:
                user = row.get("User", "")
                host = row.get("Host", "%")
                users.append({
                    "user": user,
                    "host": host,
                    "account_locked": bool(row.get("account_locked", 0)),
                    "password_expired": bool(row.get("password_expired", 0)),
                    "grants": [],
                })
            # 2. 获取每个用户的权限
            for u in users:
                if u["user"] in ("root", "mysql.sys", "mysql.session", "mysql.infoschema"):
                    u["grants"] = ["ALL PRIVILEGES"]
                    continue
                try:
                    g_rows = _exec_select(ops, conn_data,
                        f"SHOW GRANTS FOR '{u['user']}'@'{u['host']}'")
                    for g in g_rows:
                        val = g.get("Grants for {}@{}".format(u['user'], u['host']), "") or \
                              list(g.values())[0] if g else ""
                        if val:
                            u["grants"].append(val)
                except Exception:
                    u["grants"] = ["-- 无法读取权限 (可能需要额外权限)"]

        elif db_type == "PostgreSQL":
            rows = _exec_select(ops, conn_data, "SELECT rolname FROM pg_roles ORDER BY rolname")
            for row in rows:
                users.append({
                    "user": row.get("rolname", ""),
                    "host": "",
                    "account_locked": False,
                    "password_expired": False,
                    "grants": [],
                })

        return {"success": True, "data": users}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{conn_id}/{user_name}/grants")
def get_user_grants(
    conn_id: int,
    user_name: str,
    host: str = "%",
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """获取单个用户的详细权限"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")

        if db_type == "MySQL":
            rows = _exec_select(ops, conn_data,
                f"SHOW GRANTS FOR '{user_name}'@'{host}'")
            grants = []
            for row in rows:
                val = list(row.values())[0] if row else ""
                if val:
                    grants.append(val)
            return {"success": True, "data": grants}
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/grant")
def grant_privilege(
    conn_id: int,
    body: dict,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """授予权限: {user, host, database, table, privilege, with_grant}"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        user = body.get("user", "")
        host = body.get("host", "%")
        database = body.get("database", "*")
        table = body.get("table", "*")
        privilege = body.get("privilege", "ALL PRIVILEGES")
        with_grant = body.get("with_grant", False)

        sql = f"GRANT {privilege} ON `{database}`.`{table}` TO '{user}'@'{host}'"
        if with_grant:
            sql += " WITH GRANT OPTION"

        ops.execute_sql(conn_data, sql)
        return {"success": True, "message": f"已授予 {privilege} 给 {user}@{host}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/revoke")
def revoke_privilege(
    conn_id: int,
    body: dict,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """回收权限"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        user = body.get("user", "")
        host = body.get("host", "%")
        database = body.get("database", "*")
        table = body.get("table", "*")
        privilege = body.get("privilege", "ALL PRIVILEGES")

        sql = f"REVOKE {privilege} ON `{database}`.`{table}` FROM '{user}'@'{host}'"
        ops.execute_sql(conn_data, sql)
        return {"success": True, "message": f"已回收 {privilege} 从 {user}@{host}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/create-user")
def create_user(
    conn_id: int,
    body: dict,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """创建用户"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        user = body.get("user", "")
        host = body.get("host", "%")
        password = body.get("password", "")

        if not user:
            return {"success": False, "message": "用户名不能为空"}

        sql = f"CREATE USER '{user}'@'{host}' IDENTIFIED BY '{password}'" if password else f"CREATE USER '{user}'@'{host}'"
        ops.execute_sql(conn_data, sql)
        return {"success": True, "message": f"用户 {user}@{host} 已创建"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}/{user_name}")
def drop_user(
    conn_id: int,
    user_name: str,
    host: str = "%",
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """删除用户"""
    try:
        conn_data = _get_conn_data(conn_id, storage)
        sql = f"DROP USER '{user_name}'@'{host}'"
        ops.execute_sql(conn_data, sql)
        return {"success": True, "message": f"用户 {user_name}@{host} 已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}
