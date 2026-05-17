"""数据库同步 API —— 跨库表结构 / 数据同步与历史记录"""

import os
import json
import threading
import queue
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_db_storage, get_db_ops
from ..schemas import SyncRequest, MessageResponse
from core.db_operations import DBOperations
from core.syncer import DatabaseSyncer
from models.db_storage import DBStorage
from models.sync_history import SyncHistoryManager

router = APIRouter(prefix="/api/sync", tags=["同步"])

SYNC_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "sync_logs",
)


def _ensure_log_dir():
    os.makedirs(SYNC_LOG_DIR, exist_ok=True)


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"连接 {conn_id} 不存在")
    return conn


@router.post("/start")
def sync_start(body: SyncRequest, storage: DBStorage = Depends(get_db_storage)):
    """发起数据库同步"""
    # 获取源和目标连接信息
    source_conn = _get_conn_data(body.source_conn_id, storage)
    target_conn = _get_conn_data(body.target_conn_id, storage)

    # 校验数据类型一致
    if source_conn.get("db_type") != target_conn.get("db_type"):
        raise HTTPException(
            status_code=400,
            detail="源数据库和目标数据库类型不一致，无法同步",
        )

    _ensure_log_dir()

    # 收集表列表
    tables = body.tables if body.tables else []

    # 构建 options
    options = {
        "tables": tables,
        "sync_structure": body.sync_structure,
        "sync_data": body.sync_data,
        "conflict_strategy": "overwrite" if body.drop_target else body.conflict_strategy,
    }

    # 创建日志文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"sync_{body.source_db}_{body.target_db}_{ts}.log"
    log_path = os.path.join(SYNC_LOG_DIR, log_filename)

    # 保存同步记录
    record = {
        "start_time": datetime.now().isoformat(),
        "end_time": "",
        "source_conn_id": body.source_conn_id,
        "source_db": body.source_db,
        "target_conn_id": body.target_conn_id,
        "target_db": body.target_db,
        "tables": tables,
        "sync_structure": body.sync_structure,
        "sync_data": body.sync_data,
        "status": "running",
        "log_path": log_path,
        "error_summary": "",
    }
    record_id = SyncHistoryManager.save_record(record)

    try:
        progress_queue = queue.Queue()
        cancel_event = threading.Event()

        syncer = DatabaseSyncer(
            source_conn_data=source_conn,
            target_conn_data=target_conn,
            options=options,
            progress_callback=progress_queue.put,
            cancel_event=cancel_event,
        )

        syncer.run()

        # 检查是否有错误
        status = "success"
        error_summary = ""

        # 收集最后的状态
        while not progress_queue.empty():
            msg = progress_queue.get()
            if isinstance(msg, dict):
                if msg.get("type") == "error":
                    status = "failed"
                    error_summary = msg.get("message", "")
                elif msg.get("type") == "done":
                    pass

        SyncHistoryManager.update_record(record_id, {
            "end_time": datetime.now().isoformat(),
            "status": status,
            "error_summary": error_summary,
        })

        return {
            "success": True,
            "message": "同步完成" if status == "success" else f"同步完成（有错误）",
            "data": {
                "record_id": record_id,
                "status": status,
                "log_path": log_path,
            },
        }

    except Exception as e:
        SyncHistoryManager.update_record(record_id, {
            "end_time": datetime.now().isoformat(),
            "status": "failed",
            "error_summary": str(e),
        })
        return {
            "success": False,
            "message": f"同步失败: {e}",
            "data": {"record_id": record_id},
        }


@router.get("/history")
def sync_history(limit: int = 50):
    """获取同步历史记录"""
    try:
        records = SyncHistoryManager.get_all_records(limit=limit)
        return {
            "success": True,
            "data": records,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/history/{record_id}")
def sync_history_detail(record_id: int):
    """获取同步历史详情"""
    try:
        record = SyncHistoryManager.get_record_by_id(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"success": True, "data": record}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}
