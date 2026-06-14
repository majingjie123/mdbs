"""备份恢复 API"""

import os
import sys
import json
import time
import uuid
import threading
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, BackgroundTasks
from pydantic import BaseModel

from ..dependencies import get_db_storage, get_db_ops
from ..schemas import MessageResponse
from models.db_storage import DBStorage
from core.db_operations import DBOperations
from core.backup_manager import BackupManager

# ── 项目根目录 ─────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYNC_LOGS_DIR = os.path.join(PROJECT_ROOT, "sync_logs")

router = APIRouter(prefix="/api/backup", tags=["备份恢复"])


# ── Pydantic 请求模型 ──────────────────────────────────────

# 增量备份追踪
_INCREMENTAL_STATE: dict = {}  # key: (conn_id, database) -> {"last_backup": timestamp, "table_rows": {}}


class BackupRequest(BaseModel):
    database: Optional[str] = None
    backup_path: Optional[str] = None
    options: list[str] = ["structure", "data"]  # structure, data, views, functions, triggers, events
    incremental: bool = False  # 增量备份（仅备份变化的数据）


class RestoreRequest(BaseModel):
    file_path: str
    database: Optional[str] = None


# ── 辅助函数 ────────────────────────────────────────────────

def _get_conn_data(conn_id: int, storage: DBStorage) -> Optional[dict]:
    """获取连接完整信息（含解密密码），返回 None 表示不存在"""
    conn = storage.get_connection(conn_id)
    if not conn:
        return None
    return conn


def _ensure_sync_logs_dir():
    """确保 sync_logs 目录存在"""
    os.makedirs(SYNC_LOGS_DIR, exist_ok=True)


# ── 端点：创建备份 ─────────────────────────────────────────

@router.post("/{conn_id}/backup")
def create_backup(conn_id: int, req: BackupRequest,
                  storage: DBStorage = Depends(get_db_storage)):
    """创建数据库备份"""
    # 1. 验证连接
    conn_data = _get_conn_data(conn_id, storage)
    if not conn_data:
        return {"success": False, "message": "连接不存在"}

    # 2. 确定目标数据库
    database = req.database or conn_data.get("database")
    if not database:
        return {"success": False, "message": "未指定目标数据库"}

    # 3. 确定输出路径
    if req.backup_path:
        output_path = req.backup_path
        output_dir = os.path.dirname(os.path.abspath(output_path))
    else:
        _ensure_sync_logs_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = database.replace(" ", "_").replace("/", "_")
        filename = f"backup_{safe_name}_{timestamp}.sql"
        output_path = os.path.join(SYNC_LOGS_DIR, filename)
        output_dir = SYNC_LOGS_DIR

    # 4. 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 5. 解析选项
    options = req.options or ["structure", "data"]
    include_structure = "structure" in options
    include_data = "data" in options
    incremental = getattr(req, 'incremental', False)

    # 6. 增量备份
    if incremental:
        state_key = (conn_id, database)
        state = _INCREMENTAL_STATE.get(state_key, {})
        last_backup = state.get("last_backup")
        try:
            conn = bm._get_python_connection(conn_data, database)
            if conn_data.get("db_type") == "MySQL":
                cur = conn.cursor()
                cur.execute("SELECT TABLE_NAME, TABLE_ROWS, UPDATE_TIME FROM information_schema.tables WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'", [database])
                current_rows = {}
                for r in cur.fetchall():
                    current_rows[r[0]] = {"rows": r[1], "updated": str(r[2]) if r[2] else ""}
                prev_rows = state.get("table_rows", {})
                changed_tables = [t for t, info in current_rows.items() if t not in prev_rows or prev_rows[t].get("rows") != info["rows"]]
                state["table_rows"] = current_rows
                _INCREMENTAL_STATE[state_key] = state
            else:
                changed_tables = []
            try: conn.close()
            except: pass
        except:
            changed_tables = []

        if not changed_tables and last_backup:
            return {"success": True, "data": {"file_path": "", "file_size": 0, "tables_count": 0, "incremental": True, "changed": 0}, "message": "无变更，跳过备份"}

        state["last_backup"] = time.time()
        _INCREMENTAL_STATE[state_key] = state

        if changed_tables:
            safe_name = database.replace(" ", "_").replace("/", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(SYNC_LOGS_DIR, "incr_" + safe_name + "_" + timestamp + ".sql")

    # 7. 执行备份
    try:
        bm = BackupManager()
        success, message = bm.backup_database(
            conn_data=conn_data,
            output_path=output_path,
            database=database,
            include_data=include_data,
            include_structure=include_structure,
        )

        if success:
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

            # 统计表数量（粗略，从 SQL 文件中读取 DROP TABLE / CREATE TABLE 计数）
            tables_count = 0
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip().upper().startswith("DROP TABLE IF EXISTS"):
                            tables_count += 1

            return {
                "success": True,
                "message": "备份完成",
                "data": {
                    "file_path": output_path,
                    "file_size": file_size,
                    "tables_count": tables_count,
                }
            }
        else:
            return {"success": False, "message": message}

    except Exception as e:
        return {"success": False, "message": f"备份失败: {e}"}


# ── 端点：恢复备份 ─────────────────────────────────────────

@router.post("/{conn_id}/restore")
def restore_backup(conn_id: int, req: RestoreRequest,
                   storage: DBStorage = Depends(get_db_storage)):
    """从备份文件恢复数据库"""
    # 1. 验证连接
    conn_data = _get_conn_data(conn_id, storage)
    if not conn_data:
        return {"success": False, "message": "连接不存在"}

    # 2. 验证备份文件存在
    if not os.path.isfile(req.file_path):
        return {"success": False, "message": f"备份文件不存在: {req.file_path}"}

    # 3. 确定目标数据库
    database = req.database or conn_data.get("database")
    if not database:
        return {"success": False, "message": "未指定目标数据库"}

    # 4. 临时覆盖连接数据的数据库名（恢复目标）
    conn_data = dict(conn_data)
    conn_data["database"] = database

    # 5. 执行恢复
    try:
        bm = BackupManager()
        success, message = bm.restore_database(
            conn_data=conn_data,
            input_path=req.file_path,
        )

        if success:
            return {"success": True, "message": "恢复完成"}
        else:
            return {"success": False, "message": message}

    except Exception as e:
        return {"success": False, "message": f"恢复失败: {e}"}


# ── 端点：预览备份文件 ───────────────────────────────────

@router.get("/preview/{filename:path}")
def preview_backup(filename: str):
    """预览备份文件内容（解析 SQL 文件提取元数据）"""
    _ensure_sync_logs_dir()

    safe_name = os.path.basename(os.path.normpath(filename))
    fpath = os.path.join(SYNC_LOGS_DIR, safe_name)

    if not os.path.isfile(fpath):
        return {"success": False, "message": f"备份文件不存在: {safe_name}"}

    try:
        stat = os.stat(fpath)
        content_preview = ""
        tables = []
        total_inserts = 0
        db_name = ""
        has_structure = False
        has_data = False
        has_views = False
        has_functions = False
        has_triggers = False
        has_events = False

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            # 读取前 100 行用于分析
            for i, line in enumerate(f):
                if i > 5000:
                    break
                stripped = line.strip()

                if stripped.upper().startswith("USE `"):
                    db_name = stripped.split("`")[1] if "`" in stripped else ""

                if stripped.upper().startswith("CREATE TABLE"):
                    has_structure = True
                    table_name = ""
                    if "`" in stripped:
                        parts = stripped.split("`")
                        table_name = parts[1] if len(parts) > 1 else ""
                    elif " " in stripped:
                        table_name = stripped.split()[-1]
                    tables.append({"name": table_name, "type": "table"})

                if stripped.upper().startswith("CREATE VIEW"):
                    has_views = True
                    view_name = stripped.split("`")[1] if "`" in stripped else ""
                    tables.append({"name": view_name, "type": "view"})

                if stripped.upper().startswith("CREATE FUNCTION") or stripped.upper().startswith("CREATE PROCEDURE"):
                    has_functions = True

                if stripped.upper().startswith("CREATE TRIGGER"):
                    has_triggers = True

                if stripped.upper().startswith("CREATE EVENT"):
                    has_events = True

                if stripped.upper().startswith("INSERT INTO"):
                    has_data = True
                    total_inserts += 1

            # 获取内容预览（前 20 行）
            f.seek(0)
            first_lines = []
            for i, line in enumerate(f):
                if i >= 20:
                    break
                first_lines.append(line.rstrip("\n"))
            content_preview = "\n".join(first_lines)

        # 推断备份选项
        options = []
        if has_structure:
            options.append("structure")
        if has_data:
            options.append("data")
        if has_views:
            options.append("views")
        if has_functions:
            options.append("functions")
        if has_triggers:
            options.append("triggers")
        if has_events:
            options.append("events")

        return {
            "success": True,
            "data": {
                "filename": safe_name,
                "file_size": stat.st_size,
                "file_size_display": f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024 * 1024 else f"{stat.st_size / 1024 / 1024:.2f} MB",
                "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "database": db_name,
                "tables": tables,
                "total_inserts": total_inserts,
                "options": options,
                "content_preview": content_preview,
                "total_lines": max(1, sum(1 for _ in open(fpath, "r", encoding="utf-8", errors="ignore"))),
            },
        }
    except Exception as e:
        return {"success": False, "message": f"预览失败: {e}"}


# ── 端点：列出备份文件 ─────────────────────────────────────

@router.get("/{conn_id}/backups")
def list_backups(conn_id: int,
                 storage: DBStorage = Depends(get_db_storage)):
    """列出该连接相关的备份文件"""
    # 验证连接存在
    conn_data = _get_conn_data(conn_id, storage)
    if not conn_data:
        return {"success": False, "message": "连接不存在"}

    _ensure_sync_logs_dir()

    try:
        files = []
        for fname in os.listdir(SYNC_LOGS_DIR):
            if not fname.endswith(".sql"):
                continue
            fpath = os.path.join(SYNC_LOGS_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            stat = os.stat(fpath)
            files.append({
                "name": fname,
                "size": stat.st_size,
                "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

        # 按日期降序排列
        files.sort(key=lambda x: x["date"], reverse=True)

        return {"success": True, "data": files}

    except Exception as e:
        return {"success": False, "message": f"读取备份文件列表失败: {e}"}


# ── 端点：删除备份文件 ─────────────────────────────────────

@router.delete("/backups/{filename:path}")
def delete_backup(filename: str):
    """删除指定的备份文件"""
    _ensure_sync_logs_dir()

    # 防止路径穿越
    safe_name = os.path.basename(os.path.normpath(filename))
    fpath = os.path.join(SYNC_LOGS_DIR, safe_name)

    if not os.path.isfile(fpath):
        return {"success": False, "message": f"备份文件不存在: {safe_name}"}

    try:
        os.remove(fpath)
        return {"success": True, "message": f"已删除备份文件: {safe_name}"}
    except Exception as e:
        return {"success": False, "message": f"删除失败: {e}"}
