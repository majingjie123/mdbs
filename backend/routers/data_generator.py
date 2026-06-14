"""数据生成器 API — 模拟数据填充"""

import random
import re
import string
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_db_storage, get_db_ops
from core.db_operations import DBOperations
from models.db_storage import DBStorage

router = APIRouter(prefix="/api/data-generator", tags=["数据生成器"])


class GeneratorRequest(BaseModel):
    table_name: str
    row_count: int = 100
    database: str = ""
    schema: str = ""


# ── 模拟数据工具 ──────────────────────────────────────

_NAMES = [
    "张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
    "Alice", "Bob", "Charlie", "David", "Eva", "Frank", "Grace", "Henry",
    "James", "Karen", "Leo", "Mona", "Nina", "Oscar", "Paul", "Quinn",
]
_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京",
    "西安", "重庆", "天津", "苏州", "长沙", "郑州", "东莞", "青岛",
]
_EMAIL_DOMAINS = ["qq.com", "163.com", "gmail.com", "outlook.com", "yahoo.com", "company.cn"]
_COMPANIES = [
    "阿里巴巴", "腾讯科技", "字节跳动", "百度在线", "京东集团",
    "华为技术", "小米科技", "网易网络", "美团点评", "拼多多",
]
_LOREM = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt "
    "ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco "
    "laboris nisi ut aliquip ex ea commodo consequat duis aute irure dolor in reprehenderit in "
    "voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat "
    "cupidatat non proident sunt in culpa qui officia deserunt mollit anim id est laborum"
).split()


def _random_name() -> str:
    return random.choice(_NAMES)


def _random_city() -> str:
    return random.choice(_CITIES)


def _random_email() -> str:
    name = "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 10)))
    return f"{name}{random.randint(1, 999)}@{random.choice(_EMAIL_DOMAINS)}"


def _random_phone() -> str:
    prefixes = ["13", "15", "17", "18", "19"]
    return random.choice(prefixes) + "".join(random.choices(string.digits, k=9))


def _random_company() -> str:
    return random.choice(_COMPANIES)


def _random_sentence(min_w=3, max_w=15) -> str:
    return " ".join(random.choices(_LOREM, k=random.randint(min_w, max_w))).capitalize()


def _random_text() -> str:
    return ". ".join(_random_sentence(10, 25) for _ in range(random.randint(1, 3))) + "."


def _random_int(lo=0, hi=999999) -> int:
    return random.randint(lo, hi)


def _random_decimal(lo=0.0, hi=99999.99, dp=2) -> float:
    return round(random.uniform(lo, hi), dp)


def _random_date(start="2020-01-01", end="2026-12-31") -> str:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    d = s + timedelta(days=random.randint(0, (e - s).days))
    return d.strftime("%Y-%m-%d")


def _random_datetime(start="2020-01-01", end="2026-12-31") -> str:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    d = s + timedelta(days=random.randint(0, (e - s).days),
                      hours=random.randint(0, 23),
                      minutes=random.randint(0, 59),
                      seconds=random.randint(0, 59))
    return d.strftime("%Y-%m-%d %H:%M:%S")


def _random_boolean() -> int:
    return random.choice([0, 1])


def _parse_enum_values(raw: str) -> list[str]:
    m = re.search(r"enum\((.+?)\)", raw, re.IGNORECASE)
    return re.findall(r"'(.*?)'", m.group(1)) if m else []


def _parse_set_values(raw: str) -> list[str]:
    m = re.search(r"set\((.+?)\)", raw, re.IGNORECASE)
    return re.findall(r"'(.*?)'", m.group(1)) if m else []


def _infer_mock_type(raw_type: str, field_name: str) -> str:
    """根据字段名和 SQL 类型推断最佳 mock 类型"""
    tl = raw_type.lower().split("(")[0].strip()
    fn = field_name.lower()

    hints = [
        (["name", "用户名", "昵称", "姓", "名"], "name"),
        (["email", "mail", "邮箱"], "email"),
        (["phone", "mobile", "tel", "电话", "手机"], "phone"),
        (["city", "城市", "address", "地址", "location", "地区"], "city"),
        (["company", "公司", "单位", "org", "organization"], "company"),
        (["url", "website", "网站", "链接"], "url"),
        (["ip"], "ip"),
        (["id[_]?card", "身份证"], "id_card"),
        (["title", "标题", "主题", "subject"], "sentence"),
        (["content", "内容", "描述", "desc", "note", "备注", "remark", "intro"], "text"),
        (["status", "状态", "type", "类型", "category", "类别", "tag"], "enum"),
        (["price", "金额", "money", "费用", "cost", "salary", "工资", "budget"], "decimal"),
        (["count", "数量", "次数", "age", "年龄", "num", "number", "score", "grade"], "int"),
        (["date", "日期", "时间", "time", "birth", "生日",
          "created_at", "updated_at", "create_time", "update_time"], "datetime"),
        (["flag", "is_", "has_", "enable", "disabled", "active", "visible"], "boolean"),
        (["password", "pwd", "hash", "token", "secret"], "password"),
        (["avatar", "image", "img", "photo", "pic"], "url"),
    ]
    for kw_list, mt in hints:
        for kw in kw_list:
            if kw in fn or (kw.endswith("_") and fn.startswith(kw)):
                return mt

    type_map = {
        "int": "int", "tinyint": "int", "smallint": "int",
        "mediumint": "int", "bigint": "int",
        "decimal": "decimal", "float": "decimal", "double": "decimal",
        "numeric": "decimal", "real": "decimal",
        "char": "sentence", "varchar": "sentence",
        "text": "text", "tinytext": "text", "mediumtext": "text", "longtext": "text",
        "date": "date", "datetime": "datetime", "timestamp": "datetime",
        "time": "time", "year": "int",
        "boolean": "boolean", "bool": "boolean", "bit": "boolean",
        "enum": "enum", "set": "set",
        "json": "json",
        "blob": "binary", "tinyblob": "binary", "mediumblob": "binary", "longblob": "binary",
    }
    return type_map.get(tl, "sentence")


def _generate_value(mock_type: str, raw_type: str, nullable: bool) -> Any:
    if nullable and random.random() < 0.25:
        return None

    if mock_type == "name":
        return _random_name()
    elif mock_type == "email":
        return _random_email()
    elif mock_type == "phone":
        return _random_phone()
    elif mock_type == "city":
        return _random_city()
    elif mock_type == "company":
        return _random_company()
    elif mock_type == "url":
        return f"https://www.{_random_sentence(1, 2).replace(' ', '')}.com"
    elif mock_type == "ip":
        return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"
    elif mock_type == "id_card":
        return (f"{random.randint(110000,659000)}"
                f"{random.randint(1900,2020):04d}{random.randint(1,12):02d}{random.randint(1,28):02d}"
                f"{random.randint(1000,9999):04d}")
    elif mock_type == "sentence":
        max_len = 100
        m = re.search(r"varchar\((\d+)\)", raw_type, re.IGNORECASE)
        if m:
            max_len = int(m.group(1))
        s = _random_sentence(3, 10)
        return s[:max_len] if len(s) > max_len else s
    elif mock_type == "text":
        return _random_text()
    elif mock_type == "int":
        return _random_int(0, 9999)
    elif mock_type == "decimal":
        return _random_decimal(0, 9999.99, 2)
    elif mock_type == "date":
        return _random_date()
    elif mock_type == "datetime":
        return _random_datetime()
    elif mock_type == "time":
        return f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"
    elif mock_type == "boolean":
        return _random_boolean()
    elif mock_type == "enum":
        vals = _parse_enum_values(raw_type)
        return random.choice(vals) if vals else _random_sentence(1, 3)
    elif mock_type == "set":
        vals = _parse_set_values(raw_type)
        if vals:
            return ",".join(random.sample(vals, random.randint(1, min(3, len(vals)))))
        return _random_sentence(1, 3)
    elif mock_type == "json":
        import json
        return json.dumps({"key": _random_sentence(2, 4), "value": _random_int()})
    elif mock_type == "password":
        return "".join(random.choices(string.ascii_letters + string.digits, k=12))
    return _random_sentence(3, 8)


# ── API ───────────────────────────────────────────────

def _get_conn(conn_id: int, storage: DBStorage):
    conn = storage.get_connection(conn_id)
    if not conn:
        raise HTTPException(404, "连接不存在")
    return conn


@router.get("/{conn_id}/columns")
def get_columns(
    conn_id: int, table_name: str, database: str = "", schema: str = "",
    storage=Depends(get_db_storage), ops=Depends(get_db_ops),
):
    """获取表字段及 mock 类型建议"""
    try:
        conn_data = _get_conn(conn_id, storage)
        cols = ops.get_table_columns_detailed(conn_data, table_name,
                                              database=database or None, schema=schema or None)
        if not cols:
            return {"success": False, "message": f"表 {table_name} 不存在"}
        result = []
        for col in cols:
            field = col.get("Field") or col.get("column_name", "")
            raw_type = col.get("Type") or col.get("data_type", "")
            result.append({
                "field": field,
                "type": raw_type,
                "nullable": (col.get("Null") or "").upper() == "YES",
                "key": col.get("Key") or "",
                "extra": col.get("Extra") or "",
                "default": col.get("Default"),
                "comment": col.get("Comment") or "",
                "mock_type": _infer_mock_type(raw_type, field),
                "enum_values": _parse_enum_values(raw_type) or _parse_set_values(raw_type),
            })
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/preview")
def preview_data(
    conn_id: int, req: GeneratorRequest,
    storage=Depends(get_db_storage), ops=Depends(get_db_ops),
):
    """预览生成的数据（最多 20 行）"""
    try:
        conn_data = _get_conn(conn_id, storage)
        cols = ops.get_table_columns_detailed(conn_data, req.table_name,
                                              database=req.database or None, schema=req.schema or None)
        if not cols:
            return {"success": False, "message": f"表 {req.table_name} 不存在"}
        if req.row_count < 1 or req.row_count > 10000:
            return {"success": False, "message": "行数须在 1~10000 之间"}

        auto_set = {i for i, c in enumerate(cols)
                    if "auto_increment" in (c.get("Extra") or "").lower()}
        meta = []
        for i, col in enumerate(cols):
            field = col.get("Field") or col.get("column_name", "")
            raw_type = col.get("Type") or col.get("data_type", "")
            meta.append({
                "field": field,
                "type": raw_type,
                "mock_type": _infer_mock_type(raw_type, field),
                "auto": i in auto_set,
                "nullable": (col.get("Null") or "").upper() == "YES",
            })

        preview = []
        for _ in range(min(req.row_count, 20)):
            row = []
            for m in meta:
                row.append(None if m["auto"] else _generate_value(m["mock_type"], m["type"], m["nullable"]))
            preview.append(row)

        return {"success": True, "data": {"columns": meta, "preview_rows": preview, "total": req.row_count}}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/{conn_id}/insert")
def insert_data(
    conn_id: int, req: GeneratorRequest,
    storage=Depends(get_db_storage), ops=Depends(get_db_ops),
):
    """生成并插入数据"""
    try:
        conn_data = _get_conn(conn_id, storage)
        db_type = conn_data.get("db_type", "MySQL")
        cols = ops.get_table_columns_detailed(conn_data, req.table_name,
                                              database=req.database or None, schema=req.schema or None)
        if not cols:
            return {"success": False, "message": f"表 {req.table_name} 不存在"}
        if req.row_count < 1 or req.row_count > 100000:
            return {"success": False, "message": "行数须在 1~100000 之间"}

        auto_set = {i for i, c in enumerate(cols)
                    if "auto_increment" in (c.get("Extra") or "").lower()}

        # 非自增字段列表
        fields = [c.get("Field") or c.get("column_name", "") for i, c in enumerate(cols) if i not in auto_set]
        if not fields:
            return {"success": False, "message": "没有可插入的字段"}

        q = "`" if db_type == "MySQL" else '"'
        tbl = f"{q}{req.table_name}{q}"
        cols_part = ",".join(f"{q}{f}{q}" for f in fields)
        sql = f"INSERT INTO {tbl} ({cols_part}) VALUES ({','.join(['%s'] * len(fields))})"

        conn = ops.get_connection(conn_data, database=req.database or None)
        total = 0
        batch_size = 500
        try:
            for start in range(0, req.row_count, batch_size):
                n = min(batch_size, req.row_count - start)
                rows = []
                for _ in range(n):
                    row = []
                    for i, c in enumerate(cols):
                        if i in auto_set:
                            continue
                        raw_type = c.get("Type") or c.get("data_type", "")
                        nullable = (c.get("Null") or "").upper() == "YES"
                        fn = c.get("Field") or c.get("column_name", "")
                        mt = _infer_mock_type(raw_type, fn)
                        row.append(_generate_value(mt, raw_type, nullable))
                    rows.append(row)

                if db_type == "MySQL":
                    with conn.cursor() as cur:
                        cur.executemany(sql, rows)
                    conn.commit()
                else:
                    for row in rows:
                        conn.run(sql, params=row)
                total += n
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            return {"success": False, "message": f"插入中断（已插入 {total} 行）: {str(e)}",
                    "data": {"inserted": total}}

        return {"success": True, "data": {"inserted": total},
                "message": f"成功插入 {total} 行到 {req.table_name}"}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}

