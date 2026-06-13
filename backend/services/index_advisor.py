"""索引建议引擎 — 解析 EXPLAIN FORMAT=JSON 并推荐缺失索引"""

import re
from typing import Optional


def analyze_explain(json_data: dict, sql: str) -> list[dict]:
    """
    解析 MySQL EXPLAIN FORMAT=JSON 输出，返回索引建议列表。
    每个建议: { table, columns, reason, suggested_sql, priority }
    """
    # 提取表名与其对应的 WHERE/ORDER BY/JOIN 条件
    # 1. 递归扫描 query_block 中的表访问信息
    tables_info = _scan_tables(json_data)
    # 2. 从原始 SQL 中提取 WHERE 和 JOIN 涉及的列
    sql_analysis = _analyze_sql(sql, tables_info)
    # 3. 生成建议
    suggestions = _generate_suggestions(tables_info, sql_analysis)
    return suggestions


def _scan_tables(node: dict) -> dict[str, dict]:
    """递归扫描 EXPLAIN JSON，收集表级别的访问信息"""
    tables = {}

    if not isinstance(node, dict):
        return tables

    # MySQL EXPLAIN FORMAT=JSON 结构
    # query_block → table (单表) 或 nested_loop → table (多表 JOIN)
    # Each table node has: table_name, access_type, possible_keys, key, used_key_parts, 
    # rows, filtered, attached_condition, etc.

    for key, value in node.items():
        if key == "table":
            table_info = {
                "table_name": value.get("table_name", "?"),
                "access_type": value.get("access_type", ""),
                "possible_keys": value.get("possible_keys", []),
                "key": value.get("key", ""),
                "key_length": value.get("key_length", ""),
                "rows_examined_per_avg": value.get("rows_examined_per_avg", 0),
                "rows_produced_per_avg": value.get("rows_produced_per_avg", 0),
                "filtered": value.get("filtered", 100),
                "attached_condition": value.get("attached_condition", ""),
                "used_columns": value.get("used_columns", []),
                "used_key_parts": value.get("used_key_parts", []),
            }
            # Nested-loop join 的依赖关系
            if "table_name" in value:
                tables[value["table_name"]] = table_info
        elif key == "query_block":
            # 递归扫描子查询
            subtables = _scan_tables(value)
            # 检查 nested_loop 中的表
            tables.update(subtables)
        elif key == "nested_loop":
            # MySQL 8.0 EXPLAIN FORMAT=JSON nested_loop 结构
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        tables.update(_scan_tables(item))
            elif isinstance(value, dict):
                tables.update(_scan_tables(value))
        elif key == "union_result":
            tables.update(_scan_tables(value))
        elif key == "table_name":
            pass  # 已在上层处理
        elif isinstance(value, dict):
            tables.update(_scan_tables(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    tables.update(_scan_tables(item))

    return tables


def _analyze_sql(sql: str, tables_info: dict) -> dict:
    """从 SQL 文本中提取 WHERE 列、JOIN 列、ORDER BY 列"""
    analysis = {
        "where_columns": {},    # { table: [columns] }
        "join_columns": {},     # { table: [columns] }
        "order_columns": {},    # { table: [columns] }
        "group_columns": {},    # { table: [columns] }
    }

    # 从 WHERE 中提取表名.列名
    where_patterns = re.findall(r'(\w+\.\w+)', sql, re.IGNORECASE)
    # 从 ORDER BY / GROUP BY 中提取
    order_match = re.search(r'ORDER\s+BY\s+(.+?)(?:LIMIT|HAVING|$)', sql, re.IGNORECASE)
    group_match = re.search(r'GROUP\s+BY\s+(.+?)(?:HAVING|ORDER|LIMIT|$)', sql, re.IGNORECASE)
    join_match = re.findall(r'JOIN\s+(?:(\w+)\s+)?(\w+)\s+ON\s+(.+?)(?:\s+(?:LEFT|RIGHT|INNER|OUTER|CROSS|JOIN|WHERE|GROUP|ORDER|LIMIT|$))', sql, re.IGNORECASE)

    # 从 WHERE / JOIN 条件中提取列引用
    for ref in where_patterns:
        parts = ref.split(".")
        if len(parts) == 2:
            tbl, col = parts[0].strip("`'\""), parts[1].strip("`'\"")
            if tbl not in analysis["where_columns"]:
                analysis["where_columns"][tbl] = []
            if col not in analysis["where_columns"][tbl]:
                analysis["where_columns"][tbl].append(col)

    # JOIN ON 条件
    # MySQL JOIN 语法: LEFT JOIN t2 ON t1.id = t2.t1_id
    for match in join_match:
        table_name = match[1] if match[1] else match[0]
        condition = match[2]
        col_refs = re.findall(r'(\w+)\.(\w+)', condition)
        for tbl, col in col_refs:
            if tbl not in analysis["join_columns"]:
                analysis["join_columns"][tbl] = []
            if col not in analysis["join_columns"][tbl]:
                analysis["join_columns"][tbl].append(col)

    # ORDER BY 列
    if order_match:
        order_clause = order_match.group(1)
        order_cols = re.findall(r'(\w+)\.(\w+)', order_clause)
        for tbl, col in order_cols:
            if tbl not in analysis["order_columns"]:
                analysis["order_columns"][tbl] = []
            if col not in analysis["order_columns"][tbl]:
                analysis["order_columns"][tbl].append(col)
        # 也捕获不带表名前缀的列
        bare_cols = re.findall(r'(?:^|,)\s*`?(\w+)`?\s*(?:ASC|DESC)?', order_clause)
        for col in bare_cols:
            if col.lower() not in ("asc", "desc"):
                # 无法确定表，标记为通配
                if "*" not in analysis["order_columns"]:
                    analysis["order_columns"]["*"] = []
                if col not in analysis["order_columns"]["*"]:
                    analysis["order_columns"]["*"].append(col)

    # GROUP BY 列
    if group_match:
        group_clause = group_match.group(1)
        group_cols = re.findall(r'(\w+)\.(\w+)', group_clause)
        for tbl, col in group_cols:
            if tbl not in analysis["group_columns"]:
                analysis["group_columns"][tbl] = []
            if col not in analysis["group_columns"][tbl]:
                analysis["group_columns"][tbl].append(col)

    return analysis


def _generate_suggestions(tables_info: dict, sql_analysis: dict) -> list[dict]:
    """根据表访问信息和 SQL 分析生成索引建议"""
    suggestions = []

    for table_name, info in tables_info.items():
        access_type = info.get("access_type", "")
        rows = info.get("rows_examined_per_avg", 0)
        filtered = info.get("filtered", 100)
        attached_condition = info.get("attached_condition", "")
        possible_keys = info.get("possible_keys", []) or []
        used_key = info.get("key", "") or ""
        used_key_parts = info.get("used_key_parts", []) or []

        priority = "low"

        # 规则 1: 全表扫描 (ALL) + 行数多 → 强烈建议
        if access_type == "ALL" and rows > 100:
            cols = _find_relevant_columns(table_name, info, attached_condition, sql_analysis)
            if cols:
                priority = "high" if rows > 10000 else "medium"
                suggestions.append({
                    "table": table_name,
                    "columns": cols,
                    "reason": f"全表扫描 (ALL)，预估扫描 {rows} 行，过滤后 {filtered:.0f}%。"
                              f"条件: {attached_condition[:120] if attached_condition else '无条件'}",
                    "suggested_sql": _make_create_index(table_name, cols, "idx"),
                    "priority": priority,
                })

        # 规则 2: 没有使用索引 (possible_keys 为空且非唯一扫描)
        elif access_type in ("ref", "range", "index_merge") and rows > 100:
            # 使用了索引但扫描行数多，可能索引选择不够好
            cols = _find_relevant_columns(table_name, info, attached_condition, sql_analysis)
            if cols and used_key:
                missing = [c for c in cols if c not in used_key_parts]
                if missing:
                    suggestions.append({
                        "table": table_name,
                        "columns": missing,
                        "reason": f"使用了索引 `{used_key}`，但条件中包含未索引的列: {', '.join(missing)}。"
                                  f"覆盖索引可减少回表查询。扫描 {rows} 行。",
                        "suggested_sql": _make_create_index(table_name, list(set(list(used_key_parts) + missing)), "idx_cover"),
                        "priority": "medium",
                    })

        # 规则 3: Using filesort → 需要排序索引
        if "Using filesort" in attached_condition or "filesort" in attached_condition:
            order_cols = sql_analysis.get("order_columns", {}).get(table_name, [])
            if not order_cols:
                order_cols = sql_analysis.get("order_columns", {}).get("*", [])
            if order_cols:
                suggestions.append({
                    "table": table_name,
                    "columns": order_cols,
                    "reason": f"Using filesort，ORDER BY 列: {', '.join(order_cols)}。"
                              f"添加排序索引可避免文件排序。",
                    "suggested_sql": _make_create_index(table_name, order_cols, "idx_sort"),
                    "priority": "medium",
                })

        # 规则 4: Using temporary → GROUP BY 需要索引
        if "Using temporary" in attached_condition:
            group_cols = sql_analysis.get("group_columns", {}).get(table_name, [])
            if group_cols:
                suggestions.append({
                    "table": table_name,
                    "columns": group_cols,
                    "reason": f"Using temporary，GROUP BY 列: {', '.join(group_cols)}。"
                              f"添加索引可避免临时表。",
                    "suggested_sql": _make_create_index(table_name, group_cols, "idx_group"),
                    "priority": "medium",
                })

    # 去重: 相同表列的只保留最高优先级的一条
    seen = set()
    deduped = []
    for s in sorted(suggestions, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]]):
        key = (s["table"], tuple(s["columns"]))
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped


def _find_relevant_columns(table_name: str, info: dict, attached_condition: str, sql_analysis: dict) -> list[str]:
    """从 WHERE/JOIN 条件中找出该表的候选索引列"""
    cols = set()

    # 从 attached_condition 中提取列
    if attached_condition:
        # 匹配 ..table_name.col_name 或 `table_name`.`col_name`
        col_refs = re.findall(r'`?' + re.escape(table_name) + r'`?\.`?(\w+)`?', attached_condition)
        for c in col_refs:
            cols.add(c)
        # 也匹配裸列名（当只有一张表时）
        if len(cols) == 0:
            bare_cols = re.findall(r'`?(\w+)`?\s*(?:<=|>=|<|>|=|!=|LIKE|IN|BETWEEN)', attached_condition, re.IGNORECASE)
            # 过滤掉 SQL 关键字
            reserved = {"AND", "OR", "NOT", "NULL", "TRUE", "FALSE", "IS", "LIKE", "IN", "BETWEEN"}
            for c in bare_cols:
                if c.upper() not in reserved:
                    cols.add(c)

    # 从 SQL 分析的 where_columns 中补充
    where_cols = sql_analysis.get("where_columns", {}).get(table_name, [])
    cols.update(where_cols)

    # 从 join_columns 中补充
    join_cols = sql_analysis.get("join_columns", {}).get(table_name, [])
    cols.update(join_cols)

    # 去掉已经是主键或已索引的列
    used_parts = info.get("used_key_parts", []) or []
    for p in used_parts:
        cols.discard(p)

    # 去掉未知列
    used_columns = info.get("used_columns", []) or []
    known_cols = [c for c in cols if not used_columns or c in used_columns]
    if not known_cols:
        known_cols = list(cols)

    return known_cols[:3]  # 最多建议 3 列


def _make_create_index(table: str, columns: list[str], prefix: str = "idx") -> str:
    """生成 CREATE INDEX SQL"""
    if not columns:
        return ""
    idx_name = f"{prefix}_{table}_{'_'.join(columns)}"
    idx_name = re.sub(r'[^a-zA-Z0-9_]', '', idx_name)[:64]
    cols_sql = ", ".join(f"`{c}`" for c in columns)
    return f"CREATE INDEX `{idx_name}` ON `{table}` ({cols_sql});"
