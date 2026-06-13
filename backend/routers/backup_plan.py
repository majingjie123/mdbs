"""备份计划管理 API — 定时自动备份"""

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends

from ..dependencies import get_db_storage, get_db_ops
from models.db_storage import DBStorage
from core.db_operations import DBOperations
from core.backup_manager import BackupManager

router = APIRouter(prefix="/api/backup-plans", tags=["备份计划管理"])

# ── 全局调度器 ──────────────────────────────────────────────────
_scheduler_running = False
_scheduler_thread = None


def _start_scheduler_if_needed(storage: DBStorage):
    """启动后台调度线程（全局单例）"""
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, args=(storage,), daemon=True)
    _scheduler_thread.start()


def _scheduler_loop(storage: DBStorage):
    """调度循环：每 30 秒检查一次启用的备份计划"""
    while _scheduler_running:
        try:
            now = datetime.now()
            plans = storage.list_backup_plans()
            for plan in plans:
                if not plan.get('enabled'):
                    continue
                if _should_run(plan, now):
                    # 异步执行备份（在线程中）
                    t = threading.Thread(target=_execute_plan, args=(storage, plan), daemon=True)
                    t.start()
                    # 更新 next_run
                    _update_next_run(storage, plan)
        except Exception:
            pass
        time.sleep(30)


def _should_run(plan: dict, now: datetime) -> bool:
    """判断计划是否应该现在执行"""
    schedule_type = plan.get('schedule_type', 'daily')
    schedule_value = plan.get('schedule_value', '02:00')

    # 检查 last_run，避免重复执行
    last_run = plan.get('last_run')
    if last_run:
        try:
            last = datetime.fromisoformat(last_run)
            if (now - last).total_seconds() < 60:  # 至少间隔 1 分钟
                return False
        except ValueError:
            pass

    if schedule_type == 'once':
        # 一次性：在指定时间执行
        try:
            target = datetime.fromisoformat(schedule_value)
            return abs((now - target).total_seconds()) < 60
        except ValueError:
            return False

    elif schedule_type == 'daily':
        # 每日：每天 schedule_value 时间执行 (HH:MM)
        try:
            hour, minute = map(int, schedule_value.split(':'))
            return now.hour == hour and now.minute == minute
        except (ValueError, AttributeError):
            return False

    elif schedule_type == 'weekly':
        # 每周：schedule_value = "星期几 HH:MM" 如 "1 02:00"
        try:
            parts = schedule_value.split(' ')
            target_day = int(parts[0])
            hour, minute = map(int, parts[1].split(':'))
            return now.weekday() == target_day and now.hour == hour and now.minute == minute
        except (ValueError, IndexError):
            return False

    elif schedule_type == 'interval':
        # 间隔：schedule_value = "分钟数" 如 "60"
        try:
            interval_minutes = int(schedule_value)
            if not last_run:
                return True  # 从未执行过，立即执行
            last = datetime.fromisoformat(last_run)
            return (now - last).total_seconds() >= interval_minutes * 60
        except (ValueError, AttributeError):
            return False

    return False


def _update_next_run(storage: DBStorage, plan: dict):
    """计算并更新下次运行时间"""
    now = datetime.now()
    schedule_type = plan.get('schedule_type', 'daily')
    schedule_value = plan.get('schedule_value', '02:00')

    if schedule_type == 'daily':
        try:
            hour, minute = map(int, schedule_value.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        except (ValueError, AttributeError):
            next_run = now + timedelta(hours=24)
    elif schedule_type == 'weekly':
        try:
            parts = schedule_value.split(' ')
            target_day = int(parts[0])
            hour, minute = map(int, parts[1].split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            while next_run.weekday() != target_day or next_run <= now:
                next_run += timedelta(days=1)
        except (ValueError, IndexError):
            next_run = now + timedelta(days=7)
    elif schedule_type == 'interval':
        interval = int(schedule_value)
        next_run = now + timedelta(minutes=interval)
    elif schedule_type == 'once':
        try:
            next_run = datetime.fromisoformat(schedule_value)
        except ValueError:
            next_run = now + timedelta(days=30)
    else:
        next_run = now + timedelta(hours=24)

    with sqlite3.connect(storage._db_path) as conn:
        conn.execute(
            'UPDATE backup_plans SET next_run=? WHERE id=?',
            (next_run.isoformat(timespec='seconds'), plan['id'])
        )
        conn.commit()


def _execute_plan(storage: DBStorage, plan: dict):
    """执行备份计划"""
    from ..dependencies import get_db_ops
    try:
        ops = get_db_ops()
        conn_data = storage.get_connection(plan['conn_id'])
        if not conn_data:
            return

        bm = BackupManager()
        options = plan.get('options', '["structure","data"]')
        if isinstance(options, str):
            options = json.loads(options)
        include_structure = 'structure' in options
        include_data = 'data' in options

        from ..routers.backup import SYNC_LOGS_DIR, _ensure_sync_logs_dir
        _ensure_sync_logs_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = plan['database'].replace(" ", "_").replace("/", "_")
        safe_plan = plan['name'].replace(" ", "_").replace("/", "_")
        output_path = f"{SYNC_LOGS_DIR}/backup_{safe_name}_{safe_plan}_{timestamp}.sql"

        success, _ = bm.backup_database(
            conn_data=conn_data,
            output_path=output_path,
            database=plan['database'],
            include_data=include_data,
            include_structure=include_structure,
        )

        if success:
            storage.update_backup_plan_run_time(plan['id'], 'success')
    except Exception:
        pass


# ── API 端点 ──────────────────────────────────────────────────────


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.get("")
def list_plans(
    conn_id: Optional[int] = None,
    storage: DBStorage = Depends(get_db_storage),
):
    """列出备份计划"""
    try:
        plans = storage.list_backup_plans(conn_id)
        return {"success": True, "data": plans}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    storage: DBStorage = Depends(get_db_storage),
):
    """获取单个备份计划"""
    try:
        plan = storage.get_backup_plan(plan_id)
        if not plan:
            return {"success": False, "message": "计划不存在"}
        return {"success": True, "data": plan}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("")
def create_plan(
    body: dict,
    storage: DBStorage = Depends(get_db_storage),
):
    """创建备份计划"""
    try:
        plan_id = storage.save_backup_plan(body)
        _start_scheduler_if_needed(storage)
        return {"success": True, "message": "备份计划已创建", "data": {"id": plan_id}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/{plan_id}")
def update_plan(
    plan_id: int,
    body: dict,
    storage: DBStorage = Depends(get_db_storage),
):
    """更新备份计划"""
    try:
        body['id'] = plan_id
        storage.save_backup_plan(body)
        return {"success": True, "message": "备份计划已更新"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    storage: DBStorage = Depends(get_db_storage),
):
    """删除备份计划"""
    try:
        storage.delete_backup_plan(plan_id)
        return {"success": True, "message": "备份计划已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{plan_id}/toggle")
def toggle_plan(
    plan_id: int,
    body: dict,
    storage: DBStorage = Depends(get_db_storage),
):
    """启用/禁用备份计划"""
    try:
        plan = storage.get_backup_plan(plan_id)
        if not plan:
            return {"success": False, "message": "计划不存在"}
        enable = body.get('enable', True)
        import sqlite3
        with sqlite3.connect(storage._db_path) as conn:
            conn.execute('UPDATE backup_plans SET enabled=?, updated_at=? WHERE id=?',
                         (1 if enable else True, datetime.now().isoformat(timespec='seconds'), plan_id))
            conn.commit()
        return {"success": True, "message": "备份计划已" + ("启用" if enable else "禁用")}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{plan_id}/run-now")
def run_plan_now(
    plan_id: int,
    storage: DBStorage = Depends(get_db_storage),
):
    """立即执行备份计划"""
    try:
        plan = storage.get_backup_plan(plan_id)
        if not plan:
            return {"success": False, "message": "计划不存在"}
        t = threading.Thread(target=_execute_plan, args=(storage, plan), daemon=True)
        t.start()
        return {"success": True, "message": "备份任务已启动"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# 启动调度器（模块加载时自动启动）
def init_scheduler():
    _start_scheduler_if_needed(None)  # 将在第一次请求时由依赖注入替换
