"""索引建议 API"""

from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage
from services.index_advisor import analyze_explain

router = APIRouter(prefix="/api/index-advisor", tags=["索引建议"])


@router.post("/analyze/{conn_id}")
def analyze_query(
    conn_id: int,
    body: dict,
    ops: DBOperations = Depends(get_db_ops),
    storage: DBStorage = Depends(get_db_storage),
):
    """分析 SQL 查询并返回索引建议"""
    sql = body.get("sql", "")
    if not sql:
        return {"success": False, "message": "SQL 不能为空"}

    try:
        conn_data = storage.get_connection(conn_id)
        if not conn_data:
            return {"success": False, "message": "连接不存在"}

        # 1. 执行 EXPLAIN FORMAT=JSON
        explain_sql = f"EXPLAIN FORMAT=JSON {sql}"
        columns, rows, _, is_query, _ = ops.execute_sql(
            conn_data, explain_sql, database=body.get("database")
        )

        if not rows or len(rows) == 0:
            return {"success": False, "message": "EXPLAIN 返回空结果"}

        json_data = rows[0]
        import json as _json
        if isinstance(json_data, (list, dict)):
            pass  # 已经是对象
        else:
            first_val = list(json_data.values())[0] if isinstance(json_data, dict) else json_data[0] if isinstance(json_data, (list, tuple)) else str(json_data)
            if isinstance(first_val, str):
                json_data = _json.loads(first_val)
            elif isinstance(first_val, dict):
                json_data = first_val
            else:
                json_data = _json.loads(str(first_val))

        if isinstance(json_data, str):
            json_data = _json.loads(json_data)

        # 2. 分析 EXPLAIN 输出
        suggestions = analyze_explain(json_data, sql)

        # 3. 收集基本信息
        table_count = 0
        total_rows = 0
        access_types = set()

        def _count_tables(node):
            nonlocal table_count, total_rows
            if isinstance(node, dict):
                if "table" in node:
                    table_count += 1
                    t = node["table"]
                    total_rows += t.get("rows_examined_per_avg", 0) or 0
                    access_types.add(t.get("access_type", ""))
                for v in node.values():
                    _count_tables(v)
            elif isinstance(node, list):
                for item in node:
                    _count_tables(item)

        _count_tables(json_data)

        return {"success": True, "data": {
            "suggestions": suggestions,
            "summary": {
                "table_count": table_count,
                "total_rows_examined": total_rows,
                "access_types": list(access_types),
            }
        }}
    except Exception as e:
        return {"success": False, "message": f"分析失败: {str(e)}"}
