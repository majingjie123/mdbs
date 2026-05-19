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
    schema_name: Optional[str] = None
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
    schema_name: Optional[str] = None


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


# ── 表结构修改 ────────────────────────────────────────────

class ColumnDef(BaseModel):
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    comment: str = ""
    primary_key: bool = False
    auto_increment: bool = False


class CreateTableParams(BaseModel):
    table_name: str
    columns: list[ColumnDef]
    engine: str = "InnoDB"
    charset: str = "utf8mb4"
    comment: str = ""
    database: Optional[str] = None


class AlterColumnParams(BaseModel):
    """新增或修改列的参数"""
    name: str                          # 新列名
    type: str                          # 数据类型
    nullable: bool = True
    default: Optional[str] = None
    comment: str = ""
    after: Optional[str] = None        # MySQL: 放在哪列之后
    first: bool = False                # MySQL: 放在第一列
    database: Optional[str] = None


class DropColumnParams(BaseModel):
    column_name: str
    database: Optional[str] = None


class RenameTableParams(BaseModel):
    new_name: str
    database: Optional[str] = None


# ── 导出 ─────────────────────────────────────────────────

class ExportStructureRequest(BaseModel):
    """导出表结构请求"""
    conn_id: int
    database: Optional[str] = None
    schema_name: Optional[str] = None
    format: str = "excel"                    # excel / pdf / html / markdown
    tables: list[str] = []                   # 空=全部表
    drop_table: bool = False
    if_not_exists: bool = False


class ExportERRequest(BaseModel):
    """导出 ER 图请求"""
    conn_id: int
    database: Optional[str] = None
    schema_name: Optional[str] = None
    format: str = "html"                     # html / pdf / excel / markdown
    include_relations: bool = True
    show_comments: bool = True


class ExportNavicatRequest(BaseModel):
    """导出 Navicat 连接请求"""
    conn_ids: list[int]                      # 要导出的连接 ID 列表


class ExportDataRequest(BaseModel):
    """导出表数据请求"""
    conn_id: int
    database: Optional[str] = None
    schema_name: Optional[str] = None
    table: str
    format: str = "csv"                      # csv / excel
    include_data: bool = True


# ── 导入 ─────────────────────────────────────────────────

class ParseFileResponse(BaseModel):
    """解析文件后的预览响应"""
    file_path: str                           # 后端暂存的文件路径
    columns: list[str]                       # 列名
    preview_rows: list[list[Any]]            # 前 20 行预览
    total_rows: int                          # 总行数


class ImportExecuteRequest(BaseModel):
    """执行导入请求"""
    file_path: str                           # 已上传暂存的文件路径
    conn_id: int
    database: Optional[str] = None
    schema_name: Optional[str] = None
    table_name: str                          # 目标表名
    mode: str = "append"                     # append / replace / create
    encoding: str = "utf-8"                  # 文件编码
    has_header: bool = True


# ── 同步 ─────────────────────────────────────────────────

class SyncRequest(BaseModel):
    """发起同步请求"""
    source_conn_id: int
    source_db: str = ""
    target_conn_id: int
    target_db: str = ""
    tables: list[str] = []                        # 空=全部表
    sync_structure: bool = True
    sync_data: bool = True
    drop_target: bool = False
    conflict_strategy: str = "overwrite"          # overwrite / skip


class SyncHistoryItem(BaseModel):
    id: int
    start_time: str
    end_time: str = ""
    source_conn_name: str = ""
    source_db: str = ""
    target_conn_name: str = ""
    target_db: str = ""
    tables: str = ""
    sync_structure: bool = False
    sync_data: bool = False
    status: str = ""
    log_path: str = ""
    error_summary: str = ""


# ── 备份 ─────────────────────────────────────────────────

class BackupCreateRequest(BaseModel):
    """创建备份请求"""
    database: str = ""
    backup_path: str = ""
    options: list[str] = ["structure", "data"]     # structure / data / views / functions / triggers / events


class BackupRestoreRequest(BaseModel):
    """恢复备份请求"""
    file_path: str
    database: str = ""


class BackupInfo(BaseModel):
    name: str
    size: int
    date: str
    size_display: str = ""


# ── AI 助手 ───────────────────────────────────────────────

class AIConfigBase(BaseModel):
    name: str = ""
    protocol: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    is_default: bool = False


class AIConfigCreate(AIConfigBase):
    pass


class AIConfigUpdate(BaseModel):
    name: str = ""
    protocol: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    is_default: bool = False


class AIConfigResponse(BaseModel):
    id: int
    name: str
    protocol: str
    api_key: str = ""
    base_url: str
    model: str
    system_prompt: str = ""
    temperature: float
    max_tokens: int
    is_default: bool


class ChatMessage(BaseModel):
    role: str                          # user / assistant / system
    content: str


class ChatRequest(BaseModel):
    config_id: int
    messages: list[ChatMessage]


class ChatSaveRequest(BaseModel):
    conn_id: Optional[int] = None
    db_name: Optional[str] = None
    messages: list[ChatMessage]
    context_summary: str = ""
    context_text: str = ""


class ChatHistoryItem(BaseModel):
    id: int
    conn_id: Optional[int] = None
    db_name: Optional[str] = None
    messages: list[ChatMessage] = []
    context_summary: str = ""
    created_at: str = ""
    updated_at: str = ""


class ContextBuildRequest(BaseModel):
    conn_id: int
    database: Optional[str] = None
    schema_name: Optional[str] = None
    tables: Optional[list[str]] = None


class ContextBuildResponse(BaseModel):
    context: str
    tables: int
    db_type: str = ""
    db_name: str = ""


class ListModelsRequest(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"


# ── 通用 ─────────────────────────────────────────────────

class MessageResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[Any] = None
