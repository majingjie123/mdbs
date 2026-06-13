"""数据库同步 API —— 异步执行 + 进度轮询 + 取消"""

import os
import uuid
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_db_storage
from ..schemas import SyncRequest
from core.syncer import DatabaseSyncer
from models.db_storage import DBStorage
from models.sync_history import SyncHistoryManager

router = APIRouter(prefix="/api/sync", tags=["同步"])

# ── 内存中的同步任务状态 ──
_sync_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

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


def _run_sync_task(
    task_id: str,
    source_conn: dict,
    target_conn: dict,
    options: dict,
    source_db: str,
    target_db: str,
    source_conn_id: int,
    target_conn_id: int,
    tables: list[str],
    sync_structure: bool,
    sync_data: bool,
):
    """在后台线程中执行同步任务"""
    syncer_options = {
        "tables": tables,
        "sync_structure": sync_structure,
        "sync_data": sync_data,
        "conflict_strategy": options.get("conflict_strategy", "overwrite"),
    }

    _ensure_log_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    source_label = source_db.replace(" ", "_") if source_db else "unknown"
    target_label = target_db.replace(" ", "_") if target_db else "unknown"
    log_filename = f"sync_{source_label}_{target_label}_{ts}.log"
    log_path = os.path.join(SYNC_LOG_DIR, log_filename)

    # 保存同步记录
    record = {
        "start_time": datetime.now().isoformat(),
        "end_time": "",
        "source_conn_id": source_conn_id,
        "source_db": source_db,
        "target_conn_id": target_conn_id,
        "target_db": target_db,
        "tables": tables,
        "sync_structure": sync_structure,
        "sync_data": sync_data,
        "status": "running",
        "log_path": log_path,
        "error_summary": "",
    }
    record_id = SyncHistoryManager.save_record(record)

    with _tasks_lock:
        _sync_tasks[task_id]["record_id"] = record_id
        _sync_tasks[task_id]["log_path"] = log_path

    cancel_event = threading.Event()
    with _tasks_lock:
        _sync_tasks[task_id]["cancel_event"] = cancel_event

    def progress_callback(event_type: str, data: dict):
        if event_type == "log":
            with _tasks_lock:
                logs = _sync_tasks[task_id]["logs"]
                logs.append(data)
                if len(logs) > 500:  # 最多保留 500 条日志
                    logs[:] = logs[-500:]
        elif event_type == "progress":
            with _tasks_lock:
                _sync_tasks[task_id]["progress"] = data
        elif event_type == "row_progress":
            with _tasks_lock:
                _sync_tasks[task_id]["row_progress"] = data
        elif event_type == "done":
            with _tasks_lock:
                _sync_tasks[task_id]["result"] = data

    try:
        syncer = DatabaseSyncer(
            source_conn_data=source_conn,
            target_conn_data=target_conn,
            options=syncer_options,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            source_db=source_db,
            target_db=target_db,
        )
        syncer.run()

        result = None
        with _tasks_lock:
            result = _sync_tasks[task_id].get("result", {})
        status = result.get("status", "success") if result else "success"
        error_summary = result.get("error", "") if result else ""

        with _tasks_lock:
            if _sync_tasks[task_id].get("cancel_requested"):
                status = "cancelled"

        SyncHistoryManager.update_record(record_id, {
            "end_time": datetime.now().isoformat(),
            "status": status,
            "error_summary": error_summary,
        })

        with _tasks_lock:
            _sync_tasks[task_id]["status"] = status

    except Exception as e:
        SyncHistoryManager.update_record(record_id, {
            "end_time": datetime.now().isoformat(),
            "status": "failed",
            "error_summary": str(e),
        })
        with _tasks_lock:
            _sync_tasks[task_id]["status"] = "failed"
            _sync_tasks[task_id]["error"] = str(e)

    finally:
        with _tasks_lock:
            # 清理日志以释放内存，只保留状态和结果
            _sync_tasks[task_id].pop("cancel_event", None)
            _sync_tasks[task_id].pop("logs", None)
            _sync_tasks[task_id].pop("progress", None)
            _sync_tasks[task_id].pop("row_progress", None)


@router.post("/start")
def sync_start(body: SyncRequest, storage: DBStorage = Depends(get_db_storage)):
    """发起数据库同步（后台异步执行）"""
    source_conn = _get_conn_data(body.source_conn_id, storage)
    target_conn = _get_conn_data(body.target_conn_id, storage)

    if source_conn.get("db_type") != target_conn.get("db_type"):
        raise HTTPException(
            status_code=400,
            detail="源数据库和目标数据库类型不一致，无法同步",
        )

    task_id = str(uuid.uuid4())
    total = len(body.tables) if body.tables else 0

    with _tasks_lock:
        _sync_tasks[task_id] = {
            "status": "running",
            "progress": {"table": "", "index": 0, "total": total, "percent": 0},
            "row_progress": None,
            "logs": [],
            "result": None,
            "error": "",
            "record_id": None,
            "log_path": "",
            "cancel_requested": False,
        }

    conflict_strategy = "overwrite" if body.drop_target else body.conflict_strategy

    t = threading.Thread(
        target=_run_sync_task,
        args=(
            task_id,
            source_conn,
            target_conn,
            {
                "tables": body.tables,
                "sync_structure": body.sync_structure,
                "sync_data": body.sync_data,
                "conflict_strategy": conflict_strategy,
            },
            body.source_db,
            body.target_db,
            body.source_conn_id,
            body.target_conn_id,
            body.tables,
            body.sync_structure,
            body.sync_data,
        ),
        daemon=True,
    )
    t.start()

    return {
        "success": True,
        "message": "同步任务已启动",
        "data": {"task_id": task_id},
    }


@router.get("/progress/{task_id}")
def sync_progress(task_id: str):
    """轮询同步任务进度"""
    with _tasks_lock:
        task = _sync_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": task["status"],
                "progress": task["progress"],
                "row_progress": task["row_progress"],
                "logs": task["logs"][-50:],
                "result": task["result"],
                "record_id": task["record_id"],
                "log_path": task["log_path"],
                "error": task["error"],
            },
        }


@router.post("/cancel/{task_id}")
def sync_cancel(task_id: str):
    """取消同步任务"""
    with _tasks_lock:
        task = _sync_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["status"] != "running":
            return {"success": False, "message": "任务未在运行中"}
        task["cancel_requested"] = True
        # 触发 cancel_event 让 syncer 停止
        cancel_event = task.get("cancel_event")
        if cancel_event:
            cancel_event.set()
            return {"success": True, "message": "取消请求已发送，正在终止同步..."}
        return {"success": True, "message": "取消请求已发送"}


# ── 同步历史 ──

@router.get("/history")
def sync_history(limit: int = 50):
    """获取同步历史记录"""
    try:
        records = SyncHistoryManager.get_all_records(limit=limit)
        return {"success": True, "data": records}
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


# ── 数据对比 ──

@router.post("/compare")
def sync_compare(body: SyncRequest, storage: DBStorage = Depends(get_db_storage)):
    """比对源和目标数据库的表结构/数据差异"""
    from ..dependencies import db_ops

    source_conn = _get_conn_data(body.source_conn_id, storage)
    target_conn = _get_conn_data(body.target_conn_id, storage)

    source_db = body.source_db or source_conn.get("database", "")
    target_db = body.target_db or target_conn.get("database", "")

    result = {
        "only_source": [],
        "only_target": [],
        "different": [],
        "same": [],
    }

    # 获取表列表
    try:
        src_raw = db_ops.get_tables(source_conn, database=source_db) or []
        source_tables = [t["name"] if isinstance(t, dict) else t for t in src_raw]
    except:
        source_tables = body.tables or []

    try:
        tgt_raw = db_ops.get_tables(target_conn, database=target_db) or []
        target_tables = [t["name"] if isinstance(t, dict) else t for t in tgt_raw]
    except:
        target_tables = body.tables or []

    source_set = set(source_tables)
    target_set = set(target_tables)

    result["only_source"] = sorted(source_set - target_set)
    result["only_target"] = sorted(target_set - source_set)

    # 对比共有表的数据行数
    common = sorted(source_set & target_set)
    for table in common[:50]:  # 最多对比50张表
        diff = {"table": table, "structure": [], "data": {"source": 0, "target": 0, "diff": False}}

        # 对比行数
        try:
            src_res = db_ops.execute_sql(source_conn, f"SELECT COUNT(*) as cnt FROM `{table}`", database=source_db)
            src_cnt = src_res[2] if len(src_res) > 2 else 0
            if src_res[3]:
                src_cnt = src_res[1][0][0] if src_res[1] else 0
        except:
            src_cnt = -1

        try:
            tgt_res = db_ops.execute_sql(target_conn, f"SELECT COUNT(*) as cnt FROM `{table}`", database=target_db)
            tgt_cnt = tgt_res[2] if len(tgt_res) > 2 else 0
            if tgt_res[3]:
                tgt_cnt = tgt_res[1][0][0] if tgt_res[1] else 0
        except:
            tgt_cnt = -1

        diff["data"] = {"source": src_cnt, "target": tgt_cnt, "diff": src_cnt != tgt_cnt}
        result["different"].append(diff)

    return {"success": True, "data": result}