"""AI 助手 API —— 配置管理 + 流式聊天 + 上下文构建 + 聊天历史"""

import json
import os
import sqlite3
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from dependencies import get_db_storage, get_db_ops
from schemas import (
    AIConfigCreate, AIConfigUpdate,
    ChatRequest, ChatSaveRequest,
    ContextBuildRequest, ListModelsRequest,
)
from models.db_storage import DBStorage
from core.db_operations import DBOperations

router = APIRouter(prefix="/api/ai", tags=["AI 助手"])

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "connections.db",
)


# ── 配置 CRUD ──────────────────────────────────────────────

@router.get("/configs")
def list_configs(storage: DBStorage = Depends(get_db_storage)):
    """列出所有 AI 配置"""
    try:
        configs = storage.get_ai_configs()
        result = []
        for c in configs:
            result.append({
                "id": c.get("id"),
                "name": c.get("name", ""),
                "protocol": c.get("protocol", "openai"),
                "base_url": c.get("base_url", ""),
                "model": c.get("model", ""),
                "temperature": c.get("temperature", 0.7),
                "max_tokens": c.get("max_tokens", 2048),
                "is_default": bool(c.get("is_default", False)),
                "system_prompt": c.get("system_prompt", ""),
            })
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/configs/default")
def get_default_config(storage: DBStorage = Depends(get_db_storage)):
    """获取默认 AI 配置"""
    try:
        config = storage.get_default_ai_config()
        if not config:
            return {"success": False, "message": "未设置默认配置"}
        config["is_default"] = bool(config.get("is_default", False))
        return {"success": True, "data": config}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/configs")
def create_config(req: AIConfigCreate, storage: DBStorage = Depends(get_db_storage)):
    """创建 AI 配置"""
    try:
        data = req.model_dump()
        config_id = storage.save_ai_config(data)
        return {"success": True, "data": {"id": config_id}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/configs/{config_id}")
def update_config(config_id: int, req: AIConfigUpdate, storage: DBStorage = Depends(get_db_storage)):
    """更新 AI 配置"""
    try:
        data = req.model_dump()
        data["id"] = config_id
        storage.save_ai_config(data)
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/configs/{config_id}")
def delete_config(config_id: int, storage: DBStorage = Depends(get_db_storage)):
    """删除 AI 配置"""
    try:
        storage.delete_ai_config(config_id)
        return {"success": True, "message": "配置已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── 测试连接 & 模型列表 ────────────────────────────────────

@router.post("/configs/{config_id}/test")
def test_config(config_id: int, storage: DBStorage = Depends(get_db_storage)):
    """测试 AI 配置连接"""
    try:
        from core.ai.client import AIClient
        config = storage.get_ai_config(config_id)
        if not config:
            return {"success": False, "message": "配置不存在"}
        client = AIClient(config)
        ok, msg = client.test_connection()
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/models")
def list_models(req: ListModelsRequest):
    """获取模型列表（从 API 拉取）"""
    try:
        from core.ai.client import AIClient
        ok, result = AIClient.list_models({
            "api_key": req.api_key,
            "base_url": req.base_url,
        })
        if ok:
            return {"success": True, "data": result}
        else:
            return {"success": False, "message": result}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── SS E 流式聊天 ──────────────────────────────────────────

@router.post("/chat")
async def ai_chat(req: ChatRequest, storage: DBStorage = Depends(get_db_storage)):
    """SSE 流式聊天"""
    try:
        config = storage.get_ai_config(req.config_id)
        if not config:
            return {"success": False, "message": "AI 配置不存在"}

        from core.ai.client import AIClient

        messages = [m.model_dump() for m in req.messages]

        def event_stream():
            try:
                client = AIClient(config)
                response = client.chat_completion(messages, stream=True)
                for chunk_text in response:
                    if chunk_text:
                        yield f"data: {json.dumps({'content': chunk_text})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        return {"success": False, "message": str(e)}


# ── 上下文构建 ──────────────────────────────────────────────

@router.post("/context", response_model=None)
def build_context(req: ContextBuildRequest,
                  storage: DBStorage = Depends(get_db_storage),
                  ops: DBOperations = Depends(get_db_ops)):
    """构建数据库上下文信息"""
    try:
        conn_data = storage.get_connection(req.conn_id)
        if not conn_data:
            return {"success": False, "message": "连接不存在"}

        from core.ai.context_builder import ContextBuilder
        context_text = ContextBuilder.build_context(
            db_ops=ops,
            conn_data=conn_data,
            database=req.database or conn_data.get("database", ""),
            schema=req.schema_name,
            table_names=req.tables,
        )

        # 从上下文文本中提取实际加载的表数量
        import re
        match = re.search(r'涉及 (\d+) 个表的结构信息', context_text)
        loaded_count = int(match.group(1)) if match else 0

        return {
            "success": True,
            "data": {
                "context": context_text,
                "tables": loaded_count,
                "db_type": conn_data.get("db_type", "MySQL"),
                "db_name": req.database or conn_data.get("database", ""),
            }
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── 聊天历史（直接 SQLite） ──────────────────────────────

@router.get("/history")
def list_chat_history():
    """获取聊天历史列表"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT id, conn_id, db_name, context_summary, created_at, updated_at '
                'FROM ai_chat_history ORDER BY updated_at DESC LIMIT 50'
            ).fetchall()
            result = []
            for r in rows:
                result.append({
                    "id": r["id"],
                    "conn_id": r["conn_id"],
                    "db_name": r["db_name"],
                    "context_summary": r["context_summary"] or "",
                    "created_at": r["created_at"] or "",
                    "updated_at": r["updated_at"] or "",
                })
            return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/history/{record_id}")
def get_chat_history_detail(record_id: int):
    """获取单条聊天历史详情（含完整消息）"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT * FROM ai_chat_history WHERE id=?', (record_id,)
            ).fetchone()
            if not row:
                return {"success": False, "message": "记录不存在"}
            result = dict(row)
            try:
                result["messages"] = json.loads(result.get("messages", "[]"))
            except (json.JSONDecodeError, TypeError):
                result["messages"] = []
            return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/history")
def save_chat_history(req: ChatSaveRequest):
    """保存/更新聊天历史"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        messages_json = json.dumps([m.model_dump() for m in req.messages], ensure_ascii=False)

        with sqlite3.connect(DB_PATH) as conn:
            if req.id:
                # 按 id 更新（多会话区分）
                row = conn.execute(
                    'SELECT id FROM ai_chat_history WHERE id=?', (req.id,)
                ).fetchone()
                if row:
                    conn.execute(
                        'UPDATE ai_chat_history SET messages=?, context_summary=?, context_text=?, updated_at=? WHERE id=?',
                        (messages_json, req.context_summary, req.context_text, now, row[0])
                    )
                    record_id = row[0]
                else:
                    cursor = conn.execute(
                        'INSERT INTO ai_chat_history (conn_id, db_name, messages, context_summary, context_text, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (req.conn_id, req.db_name, messages_json, req.context_summary, req.context_text, now, now)
                    )
                    record_id = cursor.lastrowid
            else:
                # 向后兼容：按 conn_id+db_name 查找
                row = conn.execute(
                    'SELECT id FROM ai_chat_history WHERE conn_id=? AND db_name IS ?',
                    (req.conn_id, req.db_name)
                ).fetchone()
                if row:
                    conn.execute(
                        'UPDATE ai_chat_history SET messages=?, context_summary=?, context_text=?, updated_at=? WHERE id=?',
                        (messages_json, req.context_summary, req.context_text, now, row[0])
                    )
                    record_id = row[0]
                else:
                    cursor = conn.execute(
                        'INSERT INTO ai_chat_history (conn_id, db_name, messages, context_summary, context_text, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (req.conn_id, req.db_name, messages_json, req.context_summary, req.context_text, now, now)
                    )
                    record_id = cursor.lastrowid
            conn.commit()

        return {"success": True, "data": {"id": record_id}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/history/{record_id}")
def delete_chat_history(record_id: int):
    """删除聊天历史"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('DELETE FROM ai_chat_history WHERE id=?', (record_id,))
            conn.commit()
        return {"success": True, "message": "记录已删除"}
    except Exception as e:
        return {"success": False, "message": str(e)}
