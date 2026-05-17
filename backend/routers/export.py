```
"""数据导出 API —— 表结构 / ER 图 / 数据 / 连接配置"""

import os
import json
import tempfile
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..dependencies import get_db_storage, get_db_ops
from ..schemas import (
    ExportStructureRequest,
    ExportERRequest,
    ExportNavicatRequest,
    ExportDataRequest,
    MessageResponse,
)
from core.db_operations import DBOperations
from models.db_storage import DBStorage
from core.exporter import Exporter

router = APIRouter(prefix="/api/export", tags=["导出"])

EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "sync_logs",
    "exports",
)


def _ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="连接不存在")
    return conn


def _collect_structures(conn_data: dict, ops: DBOperations, db: str, schema: str, tables: list[str] = None):
    """收集表结构数据"""
    all_structures = ops.get_table_structure(conn_data, database=db or None, schema=schema or None)
    if tables:
        filtered = {}
        for t in tables:
            if t in all_structures:
                filtered[t] = all_structures[t]
        return filtered
    return all_structures


@router.post("/structure")
def export_structure(body: ExportStructureRequest, storage: DBStorage = Depends(get_db_storage), ops: DBOperations = Depends(get_db_ops)):
    """导出表结构"""
    conn_data = _get_conn_data(body.conn_id, storage)
    structures = _collect_structures(conn_data, ops, body.database, body.schema, body.tables)
    if not structures:
        raise HTTPException(status_code=404, detail="未找到表结构数据")

    _ensure_export_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = body.format.lower()

    ext_map = {"excel": "xlsx", "pdf": "pdf", "html": "html", "markdown": "md"}
    ext = ext_map.get(fmt, "xlsx")
    file_path = os.path.join(EXPORT_DIR, f"table_structure_{ts}.{ext}")

    if fmt == "excel":
        Exporter.export_table_structure_to_excel(structures, file_path)
    elif fmt == "pdf":
        Exporter.export_table_structure_to_pdf(structures, file_path)
    elif fmt == "html":
        Exporter.export_table_structure_to_html(structures, file_path)
    elif fmt == "markdown":
        Exporter.export_table_structure_to_markdown(structures, file_path)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {fmt}")

    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.post("/er")
def export_er(body: ExportERRequest, storage: DBStorage = Depends(get_db_storage), ops: DBOperations = Depends(get_db_ops)):
    """导出 ER 图"""
    conn_data = _get_conn_data(body.conn_id, storage)
    structures = _collect_structures(conn_data, ops, body.database, body.schema)
    if not structures:
        raise HTTPException(status_code=404, detail="未找到表结构数据")

    relations = []
    if body.include_relations:
        rels = ops.get_relations(conn_data, database=body.database or None)
        if rels:
            relations = rels

    _ensure_export_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = body.format.lower()

    ext_map = {"excel": "xlsx", "pdf": "pdf", "html": "html", "markdown": "md"}
    ext = ext_map.get(fmt, "html")
    file_path = os.path.join(EXPORT_DIR, f"er_diagram_{ts}.{ext}")

    if fmt == "excel":
        Exporter.export_er_to_excel(structures, relations, file_path)
    elif fmt == "pdf":
        Exporter.export_er_to_pdf(structures, relations, file_path)
    elif fmt == "html":
        Exporter.export_er_to_html(structures, relations, file_path)
    elif fmt == "markdown":
        Exporter.export_er_to_markdown(structures, relations, file_path)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {fmt}")

    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.post("/navicat")
def export_navicat(body: ExportNavicatRequest, storage: DBStorage = Depends(get_db_storage)):
    """导出 Navicat 连接配置 (.ncx)"""
    connections = []
    for cid in body.conn_ids:
        conn = storage.get_connection(cid)
        if conn:
            connections.append(conn)

    if not connections:
        raise HTTPException(status_code=404, detail="未找到连接配置")

    _ensure_export_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(EXPORT_DIR, f"navicat_connections_{ts}.ncx")
    Exporter.export_to_navicat(connections, file_path)

    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.post("/data")
def export_data(body: ExportDataRequest, storage: DBStorage = Depends(get_db_storage), ops: DBOperations = Depends(get_db_ops)):
    """导出表数据"""
    conn_data = _get_conn_data(body.conn_id, storage)
    db_type = conn_data.get("db_type", "MySQL")
    quote = "`" if db_type == "MySQL" else '"'

    sql = f"SELECT * FROM {quote}{body.table}{quote}"
    try:
        cols, rows, affected, is_query = ops.execute_sql(
            conn_data, sql, database=body.database or None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询数据失败: {e}")

    _ensure_export_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = body.format.lower()

    if fmt == "csv":
        file_path = os.path.join(EXPORT_DIR, f"data_{body.table}_{ts}.csv")
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            if cols:
                f.write(",".join(f'"{c}"' for c in cols) + "\n")
            for row in rows:
                f.write(",".join(
                    f'"{str(v).replace(chr(34), chr(34)+chr(34))}"' if v is not None else ""
                    for v in row
                ) + "\n")
    elif fmt == "excel":
        file_path = os.path.join(EXPORT_DIR, f"data_{body.table}_{ts}.xlsx")
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = body.table[:31]
            if cols:
                ws.append(cols)
            for row in rows:
                ws.append([v if v is not None else None for v in row])
            wb.save(file_path)
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl 未安装，无法导出 Excel")
    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {fmt}")

    return FileResponse(file_path, filename=os.path.basename(file_path))
```