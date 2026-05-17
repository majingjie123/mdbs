"""Pydantic 模型定义 - FastAPI 请求/响应结构"""

from pydantic import BaseModel, Field
from typing import Optional, Any


# ── 连接管理 ─────────────────────────────────────────

class ConnData(BaseModel):
    id: Optional[int] = None
    db_type: str = "MySQL"  # MySQL / PostgreSQL
    name: str = ""
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""

    # SSH 隧道
    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_auth_type: str = "password"  # password / key
    ssh_password: str = ""
    ssh_key_path: str = ""
    ssh_key_phrase: str = ""
    ssh_local_port: int = 0
    ssh_remote_host: str = ""
    ssh_remote_port: int = 0


class ConnectionCreate(BaseModel):
    data: ConnData


class ConnectionUpdate(BaseModel):
    conn_id: int
    data: ConnData


class ConnectionInfo(BaseModel):
    id: int
    db_type: str
    name: str
    host: str
    port: int
    user: str
    database: str
    ssh_enabled: bool


# ── 数据库管理 ─────────────────────────────────────────

class CreateDBParams(BaseModel):
    name: str
    charset: str = "utf8mb4"
    collation: str = "utf8mb4_unicode_ci"
    owner: str = ""


# ── SQL 执行 ───────────────────────────────────────────

class ExecuteSQLRequest(BaseModel):
    conn_id: int
    sql: str
    database: Optional[str] = None
    schema: Optional[str] = None
    params: Optional[list] = None


class ExecuteSQLResponse(BaseModel):
    columns: list[str] = []
    rows: list[list[Any]] = []
    affected: int = 0
    is_query: bool = False
    error: Optional[str] = None


class BatchSQLItem(BaseModel):
    sql: str
    params: Optional[list] = None


class BatchSQLRequest(BaseModel):
    conn_id: int
    sqls: list[BatchSQLItem]
    database: Optional[str] = None
    schema: Optional[str] = None


# ── 表结构 ───────────────────────────────────────────────

class ColumnInfo(BaseModel):
    Field: str
    Type: str
    Collation: Optional[str] = ""
    Null: str = "YES"
    Key: str = ""
    Default: Optional[str] = None
    Extra: str = ""
    Comment: str = ""


class TableInfo(BaseModel):
    name: str
    comment: str = ""


class TableStructure(BaseModel):
    table_name: str
    comment: str = ""
    columns: list[ColumnInfo] = []
    indexes: list[dict] = []
    ddl: str = ""


# ── 通用 ─────────────────────────────────────────────────

class MessageResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[Any] = None
