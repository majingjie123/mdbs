"""数据导入 API —— CSV / Excel 文件解析与导入"""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from ..dependencies import get_db_storage, get_db_ops
from ..schemas import ImportExecuteRequest, BatchImportRequest, MessageResponse
from core.db_operations import DBOperations
from models.db_storage import DBStorage
from core.importer import Importer

router = APIRouter(prefix="/api/import", tags=["导入"])

IMPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "sync_logs",
    "imports",
)


def _ensure_import_dir():
    os.makedirs(IMPORT_DIR, exist_ok=True)


def _get_conn_data(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise ValueError("连接不存在")
    return conn


@router.post("/parse")
async def parse_file(
    file: UploadFile = File(...),
    has_header: bool = Form(True),
    encoding: str = Form("auto"),
    delimiter: str = Form(","),
):
    """上传并解析文件，返回列名和预览数据"""
    try:
        if not file.filename:
            return {"success": False, "message": "未选择文件"}

        _ensure_import_dir()
        ext = os.path.splitext(file.filename or "upload")[1].lower()
        save_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(IMPORT_DIR, save_name)

        # 保存上传文件
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        # 解析
        if ext == ".csv":
            enc = encoding if encoding != "auto" else None
            columns, rows_display, rows_raw = Importer.parse_csv(
                save_path, delimiter=delimiter, has_header=has_header, encoding=enc
            )
        elif ext == ".xlsx":
            columns, rows_display, rows_raw = Importer.parse_excel(
                save_path, has_header=has_header
            )
        else:
            return {"success": False, "message": f"不支持的文件格式: {ext}，仅支持 .csv 和 .xlsx"}

        return {
            "success": True,
            "data": {
                "file_path": save_path,
                "columns": columns,
                "preview_rows": rows_display[:20],
                "total_rows": len(rows_display),
            },
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/sql")
async def import_sql(
    file: UploadFile = File(...),
    conn_id: int = Form(...),
    database: str = Form(None),
    encoding: str = Form("utf-8"),
    ignore_errors: bool = Form(False),
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """上传并直接执行 SQL 文件"""
    try:
        if not file.filename:
            return {"success": False, "message": "未选择文件"}

        conn_data = _get_conn_data(conn_id, storage)

        # 保存文件
        _ensure_import_dir()
        save_name = f"{uuid.uuid4().hex}.sql"
        save_path = os.path.join(IMPORT_DIR, save_name)
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        # 读取 SQL 内容
        with open(save_path, "r", encoding=encoding, errors="replace") as f:
            sql_content = f.read()

        # 在后台线程中执行 SQL（避免阻塞事件循环）
        statements = [s.strip() for s in sql_content.replace("\r\n", "\n").split(";") if s.strip()]
        import asyncio

        def _do_import():
            executed = 0
            errors = []
            for stmt in statements:
                try:
                    ops.execute_sql(conn_data, stmt, database=database or None)
                    executed += 1
                except Exception as e:
                    if ignore_errors:
                        errors.append(str(e))
                    else:
                        raise
            return executed, errors

        executed, errors = await asyncio.get_event_loop().run_in_executor(None, _do_import)

        return {
            "success": True,
            "message": f"SQL 文件执行完毕，成功 {executed} 条" + (f"，忽略 {len(errors)} 条错误" if errors else ""),
            "data": {"affected": executed, "errors": errors[:10]},
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/execute")
def import_execute(
    body: ImportExecuteRequest,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """执行导入到数据库"""
    try:
        file_path = body.file_path
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在，请重新上传"}

        conn_data = _get_conn_data(body.conn_id, storage)

        # 解析文件
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            enc = body.encoding if body.encoding != "auto" else None
            columns, rows_display, rows_raw = Importer.parse_csv(
                file_path, has_header=body.has_header, encoding=enc
            )
        elif ext == ".xlsx":
            columns, rows_display, rows_raw = Importer.parse_excel(
                file_path, has_header=body.has_header
            )
        else:
            return {"success": False, "message": f"不支持的文件格式: {ext}"}

        if not rows_raw:
            return {"success": False, "message": "文件为空或无有效数据"}

        # 如果 mode=create，先生成并执行 CREATE TABLE
        if body.mode == "create":
            create_sql = Importer.generate_create_sql(
                body.table_name, columns, rows_raw, db_type=conn_data.get("db_type", "MySQL")
            )
            ops.execute_sql(conn_data, create_sql, database=body.database or None)

        # 执行导入
        success, result = Importer.import_to_table(
            ops, conn_data, body.table_name, columns, rows_raw,
            mode=body.mode, database=body.database or None,
        )

        if success:
            return {"success": True, "message": f"导入成功，共导入 {result} 行数据", "data": {"affected": result}}
        else:
            return {"success": False, "message": f"导入失败: {result}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/batch-parse")
async def batch_parse_files(
    files: list[UploadFile] = File(...),
    encoding: str = Form("utf-8"),
    has_header: bool = Form(True),
    delimiter: str = Form(","),
):
    """批量上传并解析多个 CSV/Excel 文件"""
    try:
        if not files:
            return {"success": False, "message": "未选择文件"}

        _ensure_import_dir()
        results = []

        for file in files:
            if not file.filename:
                continue
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in (".csv", ".xlsx"):
                results.append({
                    "filename": file.filename, "success": False,
                    "message": f"不支持的文件格式: {ext}",
                })
                continue

            save_name = f"{uuid.uuid4().hex}{ext}"
            save_path = os.path.join(IMPORT_DIR, save_name)
            content = await file.read()
            with open(save_path, "wb") as f:
                f.write(content)

            try:
                if ext == ".csv":
                    enc = encoding if encoding != "auto" else None
                    columns, rows_display, rows_raw = Importer.parse_csv(
                        save_path, delimiter=delimiter, has_header=has_header, encoding=enc
                    )
                else:
                    columns, rows_display, rows_raw = Importer.parse_excel(
                        save_path, has_header=has_header
                    )

                default_table = os.path.splitext(file.filename)[0].replace(" ", "_").replace("-", "_")
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "file_path": save_path,
                    "columns": columns,
                    "preview_rows": rows_display[:5],
                    "total_rows": len(rows_display),
                    "default_table_name": default_table,
                })
            except Exception as e:
                results.append({
                    "filename": file.filename, "success": False, "message": str(e),
                })

        return {"success": True, "data": {"files": results}}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/batch-execute")
def batch_import_execute(
    body: BatchImportRequest,
    storage: DBStorage = Depends(get_db_storage),
    ops: DBOperations = Depends(get_db_ops),
):
    """批量执行导入"""
    try:
        conn_data = _get_conn_data(body.conn_id, storage)
        results = []

        for item in body.items:
            file_path = item.file_path
            if not os.path.exists(file_path):
                results.append({
                    "table_name": item.table_name, "success": False,
                    "message": f"文件不存在: {file_path}",
                })
                continue

            try:
                ext = os.path.splitext(file_path)[1].lower()
                if ext == ".csv":
                    enc = body.encoding if body.encoding != "auto" else None
                    columns, rows_display, rows_raw = Importer.parse_csv(
                        file_path, has_header=True, encoding=enc
                    )
                elif ext == ".xlsx":
                    columns, rows_display, rows_raw = Importer.parse_excel(
                        file_path, has_header=True
                    )
                else:
                    results.append({
                        "table_name": item.table_name, "success": False,
                        "message": f"不支持的文件格式: {ext}",
                    })
                    continue

                if not rows_raw:
                    results.append({
                        "table_name": item.table_name, "success": False,
                        "message": "文件为空或无有效数据",
                    })
                    continue

                if item.mode == "create":
                    create_sql = Importer.generate_create_sql(
                        item.table_name, columns, rows_raw,
                        db_type=conn_data.get("db_type", "MySQL"),
                    )
                    ops.execute_sql(conn_data, create_sql, database=body.database or None)

                success, result = Importer.import_to_table(
                    ops, conn_data, item.table_name, columns, rows_raw,
                    mode=item.mode, database=body.database or None,
                )

                results.append({
                    "table_name": item.table_name,
                    "success": success,
                    "message": f"导入{'成功' if success else '失败'}, 处理 {result if success else result} 行",
                    "imported_rows": result if success else 0,
                })
            except Exception as e:
                results.append({
                    "table_name": item.table_name, "success": False, "message": str(e),
                })

        total = len(results)
        success_count = sum(1 for r in results if r["success"])
        return {
            "success": True,
            "message": f"批量导入完成: 成功 {success_count}/{total}",
            "data": {"results": results, "total": total, "success_count": success_count},
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
