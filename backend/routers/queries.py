"""保存的查询 CRUD API"""

from fastapi import APIRouter, Depends
from dependencies import get_db_storage
from schemas import SavedQueryCreate, SavedQueryUpdate, SavedQueryResponse
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/queries", tags=["保存的查询"])


@router.get("/{conn_id}")
def list_queries(
    conn_id: int,
    db_name: str | None = None,
    storage: DBStorage = Depends(get_db_storage),
):
    """列出某个连接下的所有保存查询"""
    try:
        items = storage.list_saved_queries(conn_id, db_name)
        return {"success": True, "data": items}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/")
def create_query(
    req: SavedQueryCreate,
    storage: DBStorage = Depends(get_db_storage),
):
    """新增保存的查询"""
    try:
        qid = storage.save_query(req.model_dump())
        return {"success": True, "data": {"id": qid}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.put("/{query_id}")
def update_query(
    query_id: int,
    req: SavedQueryUpdate,
    storage: DBStorage = Depends(get_db_storage),
):
    """更新保存的查询（名称 / SQL）"""
    try:
        data = req.model_dump(exclude_none=True)
        data["id"] = query_id
        storage.save_query(data)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/{query_id}")
def delete_query(
    query_id: int,
    storage: DBStorage = Depends(get_db_storage),
):
    """删除保存的查询"""
    try:
        storage.delete_saved_query(query_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}
