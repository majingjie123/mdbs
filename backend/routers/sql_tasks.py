"""SQL 任务计划管理 API — 定时执行 SQL"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ..dependencies import get_db_storage, get_db_ops
from models.db_storage import DBStorage
from core.db_operations import DBOperations

router = APIRouter(prefix="/api/sql-tasks", tags=["SQL 任务计划"])

_scheduler_running = False
_scheduler_thread = None


class SQLTaskRequest(BaseModel):
    conn_id: int
    name: str
    database: str = ""
    sql_text: str
    schedule_type: str = "once"
    schedule_value: str = ""
    enabled: bool = True


def _start_scheduler_if_needed(storage: DBStorage, ops: DBOperations):
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, args=(storage, ops), daemon=True
    )
    _scheduler_thread.start()


def _scheduler_loop(storage: DBStorage, ops: DBOperations):
    while _scheduler_running:
        try:
            now = datetime.now()
            tasks = storage.list_sql_tasks()
            for task in tasks:
                if not task.get("enabled"):
                    continue
                next_run = task.get("next_run")
                if next_run:
                    try:
                        if now >= datetime.fromisoformat(next_run):
                            t = threading.Thread(
                                target=_execute_task, args=(storage, ops, task), daemon=True
                            )
                            t.start()
                            _update_next_run(storage, task)
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
        time.sleep(30)


def _calculate_next_run(task: dict) -> str:
    now = datetime.now()
    st = task.get("schedule_type", "once")
    sv = task.get("schedule_value", "")
    if st == "once":
        return ""
    if st == "daily":
        try:
            parts = sv.split(":")
            h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            nr = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if nr <= now:
                nr += timedelta(days=1)
            return nr.isoformat(timespec="seconds")
        except Exception:
            return (now + timedelta(days=1)).isoformat(timespec="seconds")
    elif st == "hourly":
        try:
            m = int(sv) if sv.isdigit() else 0
            nr = now.replace(minute=m, second=0, microsecond=0)
            if nr <= now:
                nr += timedelta(hours=1)
            return nr.isoformat(timespec="seconds")
        except Exception:
            return (now + timedelta(hours=1)).isoformat(timespec="seconds")
    else:
        mins = max(1, int(sv) if sv.isdigit() else 60)
        return (now + timedelta(minutes=mins)).isoformat(timespec="seconds")


def _update_next_run(storage: DBStorage, task: dict):
    nr = _calculate_next_run(task)
    if not nr:
        with storage._get_connection() as conn:
            conn.execute(
                "UPDATE sql_tasks SET enabled=0, updated_at=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), task["id"]),
            )
            conn.commit()
        return
    with storage._get_connection() as conn:
        conn.execute(
            "UPDATE sql_tasks SET next_run=?, updated_at=? WHERE id=?",
            (nr, datetime.now().isoformat(timespec="seconds"), task["id"]),
        )
        conn.commit()


def _execute_task(storage: DBStorage, ops: DBOperations, task: dict):
    try:
        conn_data = storage.get_connection(task["conn_id"])
        if not conn_data:
            storage.update_sql_task_run_time(task["id"], "连接不存在")
            return
        _, rows, affected, is_query = ops.execute_sql(
            conn_data, task["sql_text"], database=task.get("database") or None
        )
        if is_query:
            result = "查询完成, 返回 " + str(len(rows)) + " 行"
        else:
            result = "执行成功, 影响 " + str(affected) + " 行"
        storage.update_sql_task_run_time(task["id"], result)
    except Exception as e:
        storage.update_sql_task_run_time(task["id"], "失败: " + str(e)[:200])


@router.get("/tasks")
def list_tasks(conn_id: Optional[int] = None, storage: DBStorage = Depends(get_db_storage)):
    try:
        return {"success": True, "data": storage.list_sql_tasks(conn_id)}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/tasks/{task_id}")
def get_task(task_id: int, storage: DBStorage = Depends(get_db_storage)):
    try:
        task = storage.get_sql_task(task_id)
        if not task:
            return {"success": False, "message": "task not found"}
        return {"success": True, "data": task}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/tasks")
def create_task(body: SQLTaskRequest, storage: DBStorage = Depends(get_db_storage), ops: DBOperations = Depends(get_db_ops)):
    try:
        data = body.model_dump()
        if data["schedule_type"] != "once":
            data["next_run"] = _calculate_next_run(data)
        else:
            data["next_run"] = ""
        task_id = storage.save_sql_task(data)
        _start_scheduler_if_needed(storage, ops)
        return {"success": True, "message": "task created", "data": {"id": task_id}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/tasks/{task_id}")
def update_task(task_id: int, body: SQLTaskRequest, storage: DBStorage = Depends(get_db_storage)):
    try:
        data = body.model_dump()
        data["id"] = task_id
        if data["schedule_type"] != "once":
            data["next_run"] = _calculate_next_run(data)
        else:
            data["next_run"] = ""
        storage.save_sql_task(data)
        return {"success": True, "message": "task updated"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, storage: DBStorage = Depends(get_db_storage)):
    try:
        if not storage.get_sql_task(task_id):
            return {"success": False, "message": "task not found"}
        storage.delete_sql_task(task_id)
        return {"success": True, "message": "task deleted"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/tasks/{task_id}/toggle")
def toggle_task(task_id: int, body: dict, storage: DBStorage = Depends(get_db_storage)):
    try:
        enable = body.get("enable", True)
        with storage._get_connection() as conn:
            conn.execute(
                "UPDATE sql_tasks SET enabled=?, updated_at=? WHERE id=?",
                (1 if enable else 0, datetime.now().isoformat(timespec="seconds"), task_id),
            )
            conn.commit()
        return {"success": True, "message": "task " + ("enabled" if enable else "disabled")}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/tasks/{task_id}/run-now")
def run_task_now(task_id: int, storage: DBStorage = Depends(get_db_storage), ops: DBOperations = Depends(get_db_ops)):
    try:
        task = storage.get_sql_task(task_id)
        if not task:
            return {"success": False, "message": "task not found"}
        t = threading.Thread(target=_execute_task, args=(storage, ops, task), daemon=True)
        t.start()
        return {"success": True, "message": "task started"}
    except Exception as e:
        return {"success": False, "message": str(e)}
