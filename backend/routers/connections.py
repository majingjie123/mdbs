"""连接管理 API"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from ..schemas import ConnData, ConnectionCreate, ConnectionUpdate, MessageResponse
from models.db_storage import DBStorage
from core.db_operations import DBOperations

router = APIRouter(prefix="/api/connections", tags=["连接管理"])


@router.get("/")
def list_connections(storage: DBStorage = Depends(get_db_storage)):
    """获取所有已保存的连接"""
    conns = storage.get_all_connections()
    # 脱敏：省略密码等敏感字段
    safe = []
    for c in conns:
        safe.append({
            "id": c.get("id"),
            "db_type": c.get("db_type"),
            "name": c.get("name"),
            "host": c.get("host"),
            "port": c.get("port"),
            "user": c.get("user"),
            "database": c.get("database"),
            "ssh_enabled": bool(c.get("ssh_enabled", False)),
        })
    return {"success": True, "data": safe}


@router.get("/{conn_id}")
def get_connection(conn_id: int, storage: DBStorage = Depends(get_db_storage)):
    """获取单个连接的完整信息（含解密密码）"""
    conn = storage.get_connection(conn_id)
    if not conn:
        return {"success": False, "message": "连接不存在"}
    return {"success": True, "data": conn}


@router.post("/")
def create_connection(req: ConnectionCreate, storage: DBStorage = Depends(get_db_storage)):
    """新建连接"""
    try:
        data = req.data.model_dump()
        conn_id = storage.add_connection(data)
        return {"success": True, "message": "创建成功", "data": {"id": conn_id}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/{conn_id}")
def update_connection(conn_id: int, req: ConnectionUpdate, storage: DBStorage = Depends(get_db_storage)):
    """更新连接"""
    try:
        data = req.data.model_dump()
        storage.update_connection(conn_id, data)
        return {"success": True, "message": "更新成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{conn_id}")
def delete_connection(conn_id: int, storage: DBStorage = Depends(get_db_storage)):
    """删除连接"""
    try:
        storage.delete_connection(conn_id)
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/disconnect")
def disconnect_connection(conn_id: int, ops: DBOperations = Depends(get_db_ops)):
    """断开连接，释放资源"""
    try:
        ops.disconnect(conn_id)
        return {"success": True, "message": "已断开"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/test")
def test_connection(req: ConnectionCreate, ops: DBOperations = Depends(get_db_ops)):
    """测试连接是否可用"""
    try:
        data = req.data.model_dump()
        ok, msg = ops.test_connection(data)
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}
