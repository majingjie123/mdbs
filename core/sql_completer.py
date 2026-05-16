"""
SQL 智能补全引擎 - 策略模式实现

模块说明:
- CompletionStrategy: 补全策略抽象基类
- DotCompletionStrategy: 点号触发补全 (table.column)
- ContextCompletionStrategy: 上下文补全 (空格后智能建议)
- PrefixCompletionStrategy: 前缀匹配补全
- AliasResolver: 别名解析器 (独立工具类)
- SQLCompleter: 策略调度器
"""

import re
from abc import ABC, abstractmethod
from core.metadata_cache import MetadataCache


# ================================================================
# 关键字映射常量 (替代多个 if-else)
# ================================================================

# SQL 关键字集合
SQL_KEYWORDS = frozenset({
    "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", "INTO", "VALUES",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "FULL", "ON",
    "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET",
    "AND", "OR", "NOT", "IN", "BETWEEN", "IS", "NULL", "AS", "DISTINCT",
    "CREATE", "TABLE", "DROP", "ALTER", "INDEX", "COMMIT", "ROLLBACK",
    "DESC", "ASC", "SHOW", "DATABASES", "USE", "UNION", "ALL",
    "EXISTS", "LIKE", "SET", "IF", "CASE", "WHEN", "THEN", "ELSE", "END",
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "DEFAULT",
    "VIEW", "TRIGGER", "PROCEDURE", "FUNCTION"
})

# 关键字到上下文的映射 (用于从后往前扫描时快速转换)
KEYWORD_TO_CONTEXT = {
    "FROM": "FROM",
    "JOIN": "JOIN",
    "LEFT": "JOIN",
    "RIGHT": "JOIN",
    "INNER": "JOIN",
    "OUTER": "JOIN",
    "CROSS": "JOIN",
    "FULL": "JOIN",
    "ON": "ON",
    "GROUP": "GROUP_BY",
    "ORDER": "ORDER_BY",
    "HAVING": "HAVING",
    "SELECT": "SELECT",
    "WHERE": "WHERE",
    "INTO": "INTO",
    "SET": "SET"
}

# FROM/JOIN 后不应识别为别名的关键字
POST_TABLE_KEYWORDS = frozenset({
    "ON", "WHERE", "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "FULL",
    "JOIN", "GROUP", "ORDER", "HAVING", "LIMIT", "UNION", "SET",
    "AND", "OR", "WHEN", "THEN", "ELSE", "END"
})


# ================================================================
# 补全项数据模型
# ================================================================

class CompletionItem:
    """
    补全项数据模型 - 支持分类、类型显示和智能插入
    
    Navicat 风格:
    - 按类型分颜色/图标显示 (表、字段、关键字、函数)
    - 显示字段类型信息 (INT, VARCHAR...)
    - 函数自动补全括号
    """
    
    TYPE_KEYWORD = 'keyword'
    TYPE_TABLE = 'table'
    TYPE_COLUMN = 'column'
    TYPE_FUNCTION = 'function'
    TYPE_ALIAS = 'alias'
    TYPE_DATABASE = 'database'

    def __init__(self, name, item_type=TYPE_KEYWORD, display=None, detail=None, insert_text=None):
        """
        :param name: 实际名称（补全到编辑器中的文本）
        :param item_type: 分类 (keyword/table/column/function/alias/database)
        :param display: 列表显示文本 (默认同 name)
        :param detail: 额外信息，如字段类型 "INT", 表注释 "用户表"
        :param insert_text: 插入到编辑器中的文本 (默认同 name, 函数如 "COUNT(")
        """
        self.name = name
        self.type = item_type
        self.display = display or name
        self.detail = detail or ''
        self.insert_text = insert_text or name

    def __repr__(self):
        return f"CompletionItem({self.name}, type={self.type})"


# ================================================================
# 策略基类与接口
# ================================================================

class CompletionStrategy(ABC):
    """补全策略抽象基类"""

    def __init__(self, completer):
        """
        :param completer: SQLCompleter 实例，用于访问共享数据和工具方法
        """
        self.completer = completer

    @abstractmethod
    def get_completions(self, text_before_cursor, full_statement=None):
        """
        获取补全建议
        :param text_before_cursor: 光标前的文本
        :param full_statement: 完整 SQL 语句
        :return: 补全建议列表
        """
        pass

    def _fetch_table_columns(self, table_name):
        """获取表列名（委托给主 completer）"""
        return self.completer._fetch_table_columns(table_name)

    def _fetch_table_columns_detailed(self, table_name):
        """获取表列信息含类型（委托给主 completer）"""
        return self.completer._fetch_table_columns_detailed(table_name)

    def _get_metadata(self):
        """获取元数据缓存"""
        return self.completer._get_metadata()

    def _get_current_db(self):
        """获取当前数据库名"""
        return self.completer.current_db


# ================================================================
# 别名解析器 (独立工具类)
# ================================================================

class AliasResolver:
    """
    SQL 别名解析器
    负责解析 SQL 语句中的表别名、子查询别名、CTE 别名
    """

    POST_TABLE_KEYWORDS = {
        "ON", "WHERE", "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "FULL",
        "JOIN", "GROUP", "ORDER", "HAVING", "LIMIT", "UNION", "SET",
        "AND", "OR", "WHEN", "THEN", "ELSE", "END"
    }

    SQL_KEYWORDS = [
        "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", "INTO", "VALUES",
        "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "FULL", "ON",
        "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET",
        "AND", "OR", "NOT", "IN", "BETWEEN", "IS", "NULL", "AS", "DISTINCT",
        "CREATE", "TABLE", "DROP", "ALTER", "INDEX", "COMMIT", "ROLLBACK",
        "DESC", "ASC", "SHOW", "DATABASES", "USE", "UNION", "ALL",
        "EXISTS", "LIKE", "SET", "IF", "CASE", "WHEN", "THEN", "ELSE", "END",
        "COUNT", "SUM", "AVG", "MIN", "MAX",
        "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "DEFAULT",
        "VIEW", "TRIGGER", "PROCEDURE", "FUNCTION"
    ]

    def __init__(self):
        self._cache = {}
        self._cache_sql = None

    def resolve(self, sql_text, fetch_columns_callback=None):
        """
        解析 SQL 中的别名映射
        :param sql_text: SQL 语句
        :param fetch_columns_callback: 获取表列名的回调函数 (table_name) -> [columns]
        :return: 别名映射字典 {alias: {'type': 'table'|'subquery'|'cte', 'name': str, 'columns': [str]}}
        """
        cleaned_sql = self._strip_comments(sql_text)
        if self._cache_sql == cleaned_sql:
            return self._cache

        self._cache = {}
        self._fetch_columns_callback = fetch_columns_callback

        # 1. CTE 解析
        self._cache.update(self._parse_cte_aliases(cleaned_sql))

        # 2. 子查询别名
        self._cache.update(self._parse_subquery_aliases(cleaned_sql))

        # 3. 表别名 (JOIN)
        for m in re.finditer(r'JOIN\s+([^\s\(\),]+)(?:\s+(?:AS\s+)?([a-zA-Z_]\w*))?', cleaned_sql, re.IGNORECASE):
            self._add_table_alias(m.group(1), m.group(2))

        # 4. 表别名 (FROM)
        for m in re.finditer(r'\bFROM\b', cleaned_sql, re.IGNORECASE):
            pre_text = cleaned_sql[:m.start()]
            if pre_text.count('(') != pre_text.count(')'):
                continue

            from_tail = cleaned_sql[m.end():]
            end_match = re.search(
                r'\b(WHERE|GROUP|ORDER|HAVING|LIMIT|JOIN|UNION|SET|SELECT|WITH)\b',
                from_tail, re.IGNORECASE
            )
            part_str = from_tail[:end_match.start()].strip() if end_match else from_tail.strip()

            for part in self._split_select_columns(part_str):
                part = part.strip()
                if not part or part.startswith('('):
                    continue
                m_alias = re.match(r'([^\s\(\),]+)(?:\s+(?:AS\s+)?([a-zA-Z_]\w*))?', part, re.IGNORECASE)
                if m_alias:
                    self._add_table_alias(m_alias.group(1), m_alias.group(2))

        self._cache_sql = cleaned_sql
        return self._cache

    def _add_table_alias(self, table_name, alias):
        """添加表别名到映射"""
        if not alias or alias.upper() in self.POST_TABLE_KEYWORDS or alias.upper() in self.SQL_KEYWORDS:
            if table_name not in self._cache:
                self._cache[table_name] = {'type': 'table', 'name': table_name}
        else:
            if alias not in self._cache:
                self._cache[alias] = {'type': 'table', 'name': table_name}

    def _parse_cte_aliases(self, sql_text):
        """解析 WITH 子句定义的 CTE"""
        result = {}
        if not re.search(r'\bWITH\b', sql_text, re.IGNORECASE):
            return result

        pattern = r'([a-zA-Z_]\w*)\s+AS\s*\((.*?)\)(?=\s*,|\s+SELECT|(?:\s*\)))'
        for m in re.finditer(pattern, sql_text, re.IGNORECASE | re.DOTALL):
            cte_name = m.group(1)
            subquery = m.group(2)
            columns = self._extract_subquery_columns(subquery)
            result[cte_name] = {'type': 'cte', 'columns': columns}
        return result

    def _parse_subquery_aliases(self, sql_text):
        """解析子查询别名"""
        result = {}

        for m in re.finditer(r'(?:FROM|JOIN)\s*\(', sql_text, re.IGNORECASE):
            paren_start = m.end() - 1
            depth = 1
            i = paren_start + 1

            while i < len(sql_text) and depth > 0:
                if sql_text[i] == '(':
                    depth += 1
                elif sql_text[i] == ')':
                    depth -= 1
                i += 1

            if depth != 0:
                continue

            paren_end = i - 1
            subquery = sql_text[paren_start + 1:paren_end]
            after_paren = sql_text[paren_end + 1:].strip()

            alias_match = re.match(r'(?:AS\s+)?([a-zA-Z_]\w*)', after_paren, re.IGNORECASE)
            if not alias_match:
                continue
            alias = alias_match.group(1)
            if alias.upper() in self.POST_TABLE_KEYWORDS or alias.upper() in self.SQL_KEYWORDS:
                continue

            columns = self._extract_subquery_columns(subquery)
            result[alias] = {'type': 'subquery', 'columns': columns}

        return result

    def _extract_subquery_columns(self, subquery):
        """从子查询 SELECT 提取列名"""
        match = re.search(r'SELECT\s+(.*?)\s+FROM\s+', subquery, re.IGNORECASE | re.DOTALL)
        if not match:
            return []

        select_part = match.group(1).strip()

        if select_part == '*':
            from_match = re.search(r'FROM\s+([^\s\(\),]+)', subquery, re.IGNORECASE)
            if from_match and self._fetch_columns_callback:
                return self._fetch_columns_callback(from_match.group(1))
            return []

        columns = []
        parts = self._split_select_columns(select_part)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # col AS alias
            as_match = re.match(r'.+?\s+AS\s+([a-zA-Z_]\w*)', part, re.IGNORECASE)
            if as_match:
                columns.append(as_match.group(1))
                continue

            # table.column
            if '.' in part:
                col = part.rsplit('.', 1)[-1].strip()
                col_match = re.match(r'([a-zA-Z_]\w*)', col)
                if col_match:
                    columns.append(col_match.group(1))
                continue

            # 普通列名
            col = re.match(r'([a-zA-Z_]\w*)', part)
            if col:
                columns.append(col.group(1))

        return columns

    def _split_select_columns(self, select_part):
        """按逗号分割 SELECT 列，忽略括号内逗号"""
        parts = []
        depth = 0
        current = ""

        for ch in select_part:
            if ch == '(':
                depth += 1
                current += ch
            elif ch == ')':
                depth -= 1
                current += ch
            elif ch == ',' and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += ch

        if current.strip():
            parts.append(current)
        return parts

    def _strip_comments(self, sql):
        """移除 SQL 注释"""
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        lines = []
        for line in sql.split('\n'):
            line = re.sub(r'(--|#).*$', '', line)
            lines.append(line)
        return '\n'.join(lines)

    def resolve_columns(self, alias_info, alias_map=None):
        """
        解析别名对应的列名
        :param alias_info: 别名信息 {'type': str, 'name': str, 'columns': [str]}
        :param alias_map: 别名映射表
        :return: 列名列表
        """
        if alias_info['type'] in ('subquery', 'cte'):
            return alias_info.get('columns', [])

        if alias_info['type'] == 'table':
            table_name = alias_info['name']
            # 检查是否指向 CTE
            if alias_map and table_name in alias_map:
                target = alias_map[table_name]
                if target['type'] in ('subquery', 'cte'):
                    return target.get('columns', [])

            if self._fetch_columns_callback:
                return self._fetch_columns_callback(table_name)

        return []


# ================================================================
# 策略实现
# ================================================================

class DotCompletionStrategy(CompletionStrategy):
    """
    点号触发补全策略 - Navicat 风格
    处理: db.table. / schema.table. / alias.column / table.column
    显示列名时带上字段类型，如: id (INT AUTO_INCREMENT)
    """

    def get_completions(self, text_before_cursor, full_statement=None):
        before_dot = re.split(r'[\s\n\(\),;]', text_before_cursor[:-1])
        obj_name = before_dot[-1] if before_dot else ""

        if not obj_name:
            return []

        conn_metadata = self._get_metadata()
        alias_map = self.completer.alias_resolver.resolve(
            full_statement or text_before_cursor,
            self._fetch_table_columns
        )

        # 1. 库名 -> 返回该库下的表
        if conn_metadata and obj_name in conn_metadata.get('tables', {}):
            tables = conn_metadata['tables'][obj_name]
            items = []
            for t in tables:
                if isinstance(t, dict):
                    items.append(CompletionItem(
                        t.get('name', ''), CompletionItem.TYPE_TABLE,
                        detail=t.get('comment', '')
                    ))
                else:
                    items.append(CompletionItem(t, CompletionItem.TYPE_TABLE))
            return items

        # 2. PG schema 匹配
        if conn_metadata:
            for key, tables in conn_metadata.get('tables', {}).items():
                if key.endswith(f".{obj_name}"):
                    items = []
                    for t in tables:
                        if isinstance(t, dict):
                            items.append(CompletionItem(
                                t.get('name', ''), CompletionItem.TYPE_TABLE,
                                detail=t.get('comment', '')
                            ))
                        else:
                            items.append(CompletionItem(t, CompletionItem.TYPE_TABLE))
                    return items

        # 3. 表名直接点号 -> 返回列名（带类型信息）
        if conn_metadata:
            for db_tables in conn_metadata.get('tables', {}).values():
                table_names = [t.get('name') if isinstance(t, dict) else t for t in db_tables]
                if obj_name in table_names:
                    cols_with_type = self._fetch_table_columns_detailed(obj_name)
                    if cols_with_type:
                        return sorted(cols_with_type, key=lambda x: x.name)
                    # 降级：无类型信息时返回列名
                    cols = self._fetch_table_columns(obj_name)
                    if cols:
                        return sorted([CompletionItem(c, CompletionItem.TYPE_COLUMN) for c in cols],
                                      key=lambda x: x.name)

        # 4. 别名匹配 -> 返回列名（带类型信息）
        if obj_name in alias_map:
            alias_info = alias_map[obj_name]
            if alias_info['type'] in ('subquery', 'cte'):
                col_names = self.completer.alias_resolver.resolve_columns(alias_info, alias_map)
                return sorted([CompletionItem(c, CompletionItem.TYPE_COLUMN) for c in col_names],
                              key=lambda x: x.name)
            else:
                # 表别名 - 尝试获取带类型的列信息
                table_name = alias_info.get('name', '')
                cols_with_type = self._fetch_table_columns_detailed(table_name)
                if cols_with_type:
                    return sorted(cols_with_type, key=lambda x: x.name)
                cols = self._fetch_table_columns(table_name)
                if cols:
                    return sorted([CompletionItem(c, CompletionItem.TYPE_COLUMN) for c in cols],
                                  key=lambda x: x.name)

        return []


class ContextCompletionStrategy(CompletionStrategy):
    """
    上下文补全策略 - Navicat 风格
    处理: 空格后根据 SQL 上下文返回智能建议
    特性:
    - 分类排序: 表/列优先于关键字
    - 函数补全: 聚合函数、字符串函数等
    - INSERT INTO 列列表补全
    - 列类型显示
    """

    # SQL 内置函数 (Navicat 风格)
    SQL_FUNCTIONS = [
        # 聚合函数
        ("COUNT", "聚合函数", "COUNT("),
        ("SUM", "聚合函数", "SUM("),
        ("AVG", "聚合函数", "AVG("),
        ("MAX", "聚合函数", "MAX("),
        ("MIN", "聚合函数", "MIN("),
        # 字符串函数
        ("CONCAT", "字符串函数", "CONCAT("),
        ("SUBSTRING", "字符串函数", "SUBSTRING("),
        ("TRIM", "字符串函数", "TRIM("),
        ("UPPER", "字符串函数", "UPPER("),
        ("LOWER", "字符串函数", "LOWER("),
        ("LENGTH", "字符串函数", "LENGTH("),
        ("REPLACE", "字符串函数", "REPLACE("),
        # 日期函数
        ("NOW", "日期函数", "NOW()"),
        ("CURDATE", "日期函数", "CURDATE()"),
        ("DATE_FORMAT", "日期函数", "DATE_FORMAT("),
        ("DATE_ADD", "日期函数", "DATE_ADD("),
        ("DATEDIFF", "日期函数", "DATEDIFF("),
        # 数学函数
        ("ROUND", "数学函数", "ROUND("),
        ("CEIL", "数学函数", "CEIL("),
        ("FLOOR", "数学函数", "FLOOR("),
        ("ABS", "数学函数", "ABS("),
        # 条件/转换
        ("COALESCE", "条件函数", "COALESCE("),
        ("IFNULL", "条件函数", "IFNULL("),
        ("CAST", "类型转换", "CAST("),
    ]

    # 上下文关键字映射（按顺序排列，优先显示最相关的）
    CONTEXT_KEYWORDS = {
        "FROM": ["JOIN", "WHERE", "GROUP BY", "ORDER BY"],
        "JOIN": ["ON"],
        "INTO": [],
        "SELECT": ["FROM", "DISTINCT"],
        "WHERE": ["AND", "OR", "GROUP BY", "ORDER BY", "LIMIT"],
        "ON": ["AND", "OR"],
        "HAVING": ["AND", "OR", "ORDER BY", "LIMIT"],
        "GROUP_BY": ["HAVING", "ORDER BY", "LIMIT"],
        "ORDER_BY": ["LIMIT", "ASC", "DESC"],
        "SET": ["WHERE"]
    }

    def get_completions(self, text_before_cursor, full_statement=None):
        context = self._detect_context(text_before_cursor)
        items = []

        if context in ("FROM", "JOIN", "INTO"):
            # 表优先，关键字其次
            items.extend(self._get_table_suggestions())
            for kw in self.CONTEXT_KEYWORDS.get(context, []):
                items.append(CompletionItem(kw, CompletionItem.TYPE_KEYWORD))

        elif context in ("SELECT", "WHERE", "ON", "HAVING", "GROUP_BY", "ORDER_BY", "SET"):
            # 列优先，然后函数，最后关键字
            items.extend(self._get_column_suggestions_detailed(full_statement))
            items.extend(self._get_function_suggestions())
            for kw in self.CONTEXT_KEYWORDS.get(context, []):
                items.append(CompletionItem(kw, CompletionItem.TYPE_KEYWORD))

        # INSERT INTO table (col1, col2) - 括号内列补全
        if context == "INSERT_COLS":
            items.extend(self._get_insert_column_suggestions(text_before_cursor))
            if not items:
                items.extend(self._get_column_suggestions_detailed(full_statement))

        # 保底建议
        if not items:
            for kw in ["SELECT", "FROM", "WHERE", "INSERT INTO", "UPDATE",
                        "DELETE FROM", "WITH", "CREATE TABLE", "DROP TABLE"]:
                items.append(CompletionItem(kw, CompletionItem.TYPE_KEYWORD))
            items.extend(self._get_table_suggestions()[:10])

        return self._deduplicate_items(items)

    def _deduplicate_items(self, items):
        """去重并保持顺序"""
        seen = set()
        result = []
        for item in items:
            key = item.name.upper()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _detect_context(self, text_before_cursor):
        """检测光标当前 SQL 上下文 - 使用卫语句提前返回"""
        text = text_before_cursor.rstrip()
        
        # 卫语句1: 逗号结尾 → 肯定是 SELECT 列列表
        if text.endswith(','):
            return "SELECT"
        
        # 卫语句2: ", FROM" 模式但 FROM 后没有有效表名
        if ', FROM' in text.upper():
            from_idx = text.upper().rfind(', FROM')
            after_from = text[from_idx + 7:].strip()
            if not after_from or not re.match(r'^[a-zA-Z_]', after_from):
                return "SELECT"

        # 卫语句3: 括号未闭合 → 在子查询内或 INSERT 列列表
        if text.count('(') > text.count(')'):
            return self._detect_unclosed_paren_context(text)
        
        # 卫语句4: 括号已闭合 → 检查是否是子查询
        if ')' in text:
            return self._detect_closed_subquery_context(text)

        # 默认: 扫描文本找关键字
        return self._scan_keyword_from_end(text_before_cursor)

    def _detect_unclosed_paren_context(self, text):
        """检测未闭合括号内的上下文 - 支持 INSERT 列列表"""
        last_open = text.rfind('(')
        if last_open >= 0:
            # 检查是否是 INSERT INTO table ( 模式
            before_paren = text[:last_open].rstrip()
            if re.search(r'INSERT\s+INTO\s+\S+\s*$', before_paren, re.IGNORECASE):
                return "INSERT_COLS"
            in_paren_text = text[last_open:]
            return self._detect_context_in_paren(in_paren_text)
        return None

    def _detect_closed_subquery_context(self, text):
        """检测已闭合子查询的上下文"""
        last_paren_close = text.rfind(')')
        if last_paren_close <= 0:
            return None
            
        after_paren = text[last_paren_close + 1:]
        # 检查是否是子查询别名，如 ") a"
        if not re.match(r'^\s*[a-zA-Z_]\w*\s*$', after_paren):
            return None
            
        paren_start = text.rfind('(')
        if paren_start >= 0:
            subquery_text = text[paren_start:last_paren_close + 1]
            return self._detect_context_in_paren(subquery_text)
        return None

    def _scan_keyword_from_end(self, text):
        """从文本末尾向前扫描关键字"""
        depth = 0
        i = len(text) - 1

        while i >= 0:
            ch = text[i]
            if ch == ')':
                depth += 1
            elif ch == '(':
                depth -= 1
            elif depth == 0 and (ch.isalpha() or ch == '_'):
                word = self._extract_word_at(text, i)
                if word and word in KEYWORD_TO_CONTEXT:
                    return KEYWORD_TO_CONTEXT.get(word, word)
                if word:
                    i -= len(word)
                    continue
            i -= 1

        return None

    def _extract_word_at(self, text, end_pos):
        """提取 end_pos 位置向前的一个单词"""
        start = end_pos
        while start > 0 and (text[start - 1].isalpha() or text[start - 1] == '_'):
            start -= 1
        return text[start:end_pos + 1].upper() if start <= end_pos else None

    def _detect_context_in_paren(self, subquery_text):
        """检测括号内文本的上下文 - 卫语句优化"""
        # 提取括号内的纯文本
        text = subquery_text.strip().strip('(').strip(')')
        if not text:
            return None
            
        text_upper = text.upper()
        
        # 卫语句1: 逗号结尾 → SELECT 列列表
        if text.rstrip().endswith(','):
            return "SELECT"
        
        # 卫语句2: ", FROM" 模式但 FROM 后无有效表名
        if ', FROM' in text_upper:
            from_idx = text_upper.rfind(', FROM')
            after_from = text[from_idx + 7:].strip()
            if not after_from or not re.match(r'^[a-zA-Z_]', after_from):
                return "SELECT"
        
        # 卫语句3: 只有 SELECT 没有 FROM → SELECT 列列表
        has_select = 'SELECT' in text_upper
        has_from = 'FROM' in text_upper
        
        if has_select and not has_from:
            return "SELECT"
        
        # 卫语句4: 光标在 SELECT 之后、FROM 之前
        if has_select and has_from:
            select_pos = text_upper.find('SELECT')
            from_pos = text_upper.find('FROM')
            if select_pos < from_pos:
                last_keyword = self._find_last_keyword_between(text, select_pos, from_pos)
                if last_keyword in ('SELECT', 'JOIN', 'WHERE', None):
                    return "SELECT"
        
        # 卫语句5: 扫描关键字
        keyword = self._scan_keyword_in_paren(text)
        if keyword:
            return keyword
        
        # 卫语句6: 兜底 - 有 SELECT 但没找到关键字
        if has_select:
            return "SELECT"
        
        return None

    def _find_last_keyword_between(self, text, start_pos, end_pos):
        """在指定区间内从后往前找最后一个关键字"""
        search_text = text[start_pos:end_pos]
        for i in range(len(search_text) - 1, -1, -1):
            ch = search_text[i]
            if ch.isalpha() or ch == '_':
                word = self._extract_word_at(search_text, i)
                if word and word in KEYWORD_TO_CONTEXT:
                    return word
                if word:
                    i -= len(word) - 1
        return None

    def _scan_keyword_in_paren(self, text):
        """在括号内从后往前扫描关键字"""
        depth = 0
        i = len(text) - 1
        
        while i >= 0:
            ch = text[i]
            if ch == ')':
                depth += 1
            elif ch == '(':
                depth -= 1
            elif depth == 0 and (ch.isalpha() or ch == '_'):
                word = self._extract_word_at(text, i)
                if word and word in KEYWORD_TO_CONTEXT:
                    return KEYWORD_TO_CONTEXT.get(word, word)
                if word:
                    i -= len(word) - 1
            i -= 1
        
        return None

    def _get_column_suggestions_detailed(self, full_statement):
        """获取列名建议（带类型信息）- 返回 CompletionItem 列表"""
        items = []
        alias_map = self.completer.alias_resolver.resolve(
            full_statement or "",
            self._fetch_table_columns
        )

        if alias_map:
            cols_found = False
            for alias, info in alias_map.items():
                cols = self.completer.alias_resolver.resolve_columns(info, alias_map)
                if cols:
                    cols_found = True
                    # 尝试获取带类型的列信息
                    table_name = info.get('name', '') if info['type'] == 'table' else ''
                    detailed_cols = []
                    if table_name:
                        detailed_cols = self._fetch_table_columns_detailed(table_name)
                    type_map = {dc.name.upper(): dc.detail for dc in detailed_cols}
                    
                    for col in cols:
                        col_type = type_map.get(col.upper(), '')
                        items.append(CompletionItem(
                            col, CompletionItem.TYPE_COLUMN,
                            detail=col_type
                        ))
                        items.append(CompletionItem(
                            f"{alias}.{col}", CompletionItem.TYPE_COLUMN,
                            display=f"{alias}.{col}",
                            detail=col_type
                        ))
                else:
                    items.append(CompletionItem(
                        f"{alias}.", CompletionItem.TYPE_ALIAS,
                        display=f"{alias}."
                    ))

            # 如果没有找到列，尝试从当前库的表中获取
            if not cols_found:
                conn_metadata = self._get_metadata()
                if conn_metadata:
                    for db_tables in conn_metadata.get('tables', {}).values():
                        for t in db_tables[:5]:
                            table_name = t.get('name') if isinstance(t, dict) else t
                            cols_with_type = self._fetch_table_columns_detailed(table_name)
                            if cols_with_type:
                                items.extend(cols_with_type[:30])
                            else:
                                cols = self._fetch_table_columns(table_name)
                                if cols:
                                    items.extend([CompletionItem(c, CompletionItem.TYPE_COLUMN)
                                                  for c in cols[:20]])
        else:
            conn_metadata = self._get_metadata()
            if conn_metadata:
                for db_tables in conn_metadata.get('tables', {}).values():
                    for t in db_tables[:10]:
                        table_name = t.get('name') if isinstance(t, dict) else t
                        cols_with_type = self._fetch_table_columns_detailed(table_name)
                        if cols_with_type:
                            items.extend(cols_with_type)
                            break
                    else:
                        continue
                    break

        # 补充常用关键字
        for kw in ["DISTINCT", "CASE", "NOT", "NULL", "EXISTS", "AS"]:
            items.append(CompletionItem(kw, CompletionItem.TYPE_KEYWORD))

        # 补充别名
        for alias in alias_map:
            items.append(CompletionItem(alias, CompletionItem.TYPE_ALIAS))

        return items

    def _get_function_suggestions(self):
        """获取 SQL 函数补全建议 (Navicat 风格，带括号)"""
        items = []
        for func_name, category, insert_text in self.SQL_FUNCTIONS:
            items.append(CompletionItem(
                func_name, CompletionItem.TYPE_FUNCTION,
                display=f"{func_name}()",
                detail=category,
                insert_text=insert_text
            ))
        return items

    def _get_insert_column_suggestions(self, text_before_cursor):
        """
        获取 INSERT INTO 的列补全建议
        如: INSERT INTO users (id, name, |  → 建议 remaining columns
        """
        items = []
        # 从文本中提取 INSERT INTO 的表名
        insert_match = re.search(r'INSERT\s+INTO\s+(\S+)', text_before_cursor, re.IGNORECASE)
        if not insert_match:
            return items

        table_name = insert_match.group(1)
        
        # 获取表的所有列
        cols_with_type = self._fetch_table_columns_detailed(table_name)
        if not cols_with_type:
            cols = self._fetch_table_columns(table_name)
            if cols:
                return [CompletionItem(c, CompletionItem.TYPE_COLUMN) for c in cols]
            return items

        # 获取已经写了的列名
        last_open = text_before_cursor.rfind('(')
        in_paren = text_before_cursor[last_open + 1:] if last_open >= 0 else ''
        existing_cols = set()
        for part in in_paren.split(','):
            part = part.strip()
            if part:
                existing_cols.add(part.upper())

        # 只返回未写的列
        for col_item in cols_with_type:
            if col_item.name.upper() not in existing_cols:
                items.append(col_item)

        return items

    def _get_table_suggestions(self):
        """获取表名和建议 (带备注) - 返回 CompletionItem 列表"""
        items = []
        conn_metadata = self._get_metadata()
        db = self._get_current_db() or (self.completer.conn_data.get('database') if self.completer.conn_data else None)
        
        if conn_metadata:
            # 添加数据库名
            for db_name in conn_metadata.get('dbs', []):
                items.append(CompletionItem(db_name, CompletionItem.TYPE_DATABASE))

            # 添加表名 (带备注)
            for db_name, tables in conn_metadata.get('tables', {}).items():
                for t in tables:
                    if isinstance(t, dict):
                        name = t.get('name', '')
                        comment = t.get('comment', '')
                        items.append(CompletionItem(
                            name, CompletionItem.TYPE_TABLE,
                            detail=comment
                        ))
                    else:
                        items.append(CompletionItem(t, CompletionItem.TYPE_TABLE))
        
        # 去重（保留第一个出现的）
        seen = set()
        result = []
        for item in items:
            key = item.name.upper()
            if key not in seen:
                seen.add(key)
                result.append(item)
        
        return sorted(result, key=lambda x: x.name.upper())


class PrefixCompletionStrategy(CompletionStrategy):
    """
    前缀匹配补全策略 - Navicat 风格
    处理: 有前缀时的精准上下文感知匹配
    特性:
    - 列名显示类型信息
    - 函数匹配
    - 别名.列名 补全
    - 上下文排序
    """

    KEYWORDS = [
        "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", "INTO", "VALUES",
        "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "FULL", "ON",
        "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET",
        "AND", "OR", "NOT", "IN", "BETWEEN", "IS", "NULL", "AS", "DISTINCT",
        "CREATE", "TABLE", "DROP", "ALTER", "INDEX", "COMMIT", "ROLLBACK",
        "DESC", "ASC", "SHOW", "DATABASES", "USE", "UNION", "ALL",
        "EXISTS", "LIKE", "SET", "IF", "CASE", "WHEN", "THEN", "ELSE", "END",
        "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "DEFAULT",
        "VIEW", "TRIGGER", "PROCEDURE", "FUNCTION"
    ]

    def get_completions(self, text_before_cursor, full_statement=None):
        tokens = re.split(r'[\s\n\(\),;]', text_before_cursor)
        last_token = tokens[-1] if tokens else ""

        if not last_token:
            return []

        last_token_upper = last_token.upper()
        context = self._detect_context(text_before_cursor)
        items = []

        # 1. 函数匹配 (输入前缀匹配函数名)
        items.extend(self._match_functions(last_token_upper))

        # 2. 关键字匹配
        for kw in self.KEYWORDS:
            if kw.startswith(last_token_upper):
                items.append(CompletionItem(kw, CompletionItem.TYPE_KEYWORD))

        # 3. 数据库和表名 (FROM/JOIN 上下文)
        if context in ("FROM", "JOIN", "INTO"):
            items.extend(self._match_tables_detail(last_token_upper))

        # 4. 别名和字段名 (SELECT/WHERE 等上下文)
        if context in ("SELECT", "WHERE", "ON", "HAVING", "GROUP_BY", "ORDER_BY", "SET", "INSERT_COLS", None):
            items.extend(self._match_columns_and_aliases_detail(last_token, last_token_upper, full_statement))

        # INSERT_COLS 上下文 - 补充表名列补全
        if context == "INSERT_COLS":
            insert_cols = self._get_insert_col_completions(text_before_cursor, last_token_upper)
            items.extend(insert_cols)

        # 过滤掉与输入完全相同的项
        filtered = [item for item in items if item.name.upper() != last_token_upper]
        return filtered

    def _detect_context(self, text_before_cursor):
        """检测上下文 - 复用 ContextCompletionStrategy"""
        return self.completer._strategies['context']._detect_context(text_before_cursor)

    def _match_functions(self, prefix):
        """匹配 SQL 函数"""
        items = []
        for func_name, category, insert_text in ContextCompletionStrategy.SQL_FUNCTIONS:
            if func_name.startswith(prefix):
                items.append(CompletionItem(
                    func_name, CompletionItem.TYPE_FUNCTION,
                    display=f"{func_name}()",
                    detail=category,
                    insert_text=insert_text
                ))
        return items

    def _match_tables_detail(self, prefix):
        """匹配数据库和表名 (返回 CompletionItem，带备注)"""
        items = []
        conn_metadata = self._get_metadata()

        if conn_metadata:
            # 数据库名
            for db_name in conn_metadata.get('dbs', []):
                if db_name.upper().startswith(prefix):
                    items.append(CompletionItem(db_name, CompletionItem.TYPE_DATABASE))

            # 表名 (带备注)
            for db_name, tables in conn_metadata.get('tables', {}).items():
                for t in tables:
                    if isinstance(t, dict):
                        name = t.get('name', '')
                        comment = t.get('comment', '')
                        if name.upper().startswith(prefix):
                            items.append(CompletionItem(
                                name, CompletionItem.TYPE_TABLE,
                                detail=comment
                            ))
                    elif t.upper().startswith(prefix):
                        items.append(CompletionItem(t, CompletionItem.TYPE_TABLE))

        return items

    def _match_columns_and_aliases_detail(self, last_token, last_token_upper, full_statement):
        """匹配列名和别名 (带类型信息)"""
        items = []
        alias_map = self.completer.alias_resolver.resolve(
            full_statement or "",
            self._fetch_table_columns
        )

        # 别名.column 匹配
        if '.' in last_token:
            dot_prefix, col_prefix = last_token.rsplit('.', 1)
            dot_prefix_upper = dot_prefix.upper()
            col_prefix_upper = col_prefix.upper()

            for alias, info in alias_map.items():
                if alias.upper() == dot_prefix_upper:
                    cols = self.completer.alias_resolver.resolve_columns(info, alias_map)
                    # 尝试获取带类型的列信息
                    table_name = info.get('name', '') if info['type'] == 'table' else ''
                    type_map = {}
                    if table_name:
                        detailed = self._fetch_table_columns_detailed(table_name)
                        type_map = {dc.name.upper(): dc.detail for dc in detailed}
                    
                    for c in cols:
                        if c.upper().startswith(col_prefix_upper):
                            col_type = type_map.get(c.upper(), '')
                            items.append(CompletionItem(
                                f"{alias}.{c}", CompletionItem.TYPE_COLUMN,
                                display=f"{alias}.{c}",
                                detail=col_type
                            ))
        else:
            # 建议别名
            for a in alias_map:
                if a.upper().startswith(last_token_upper):
                    alias_info = alias_map[a]
                    detail = f"-> {alias_info['name']}" if alias_info['type'] == 'table' else ''
                    items.append(CompletionItem(a, CompletionItem.TYPE_ALIAS, detail=detail))

            # 建议列名（带类型）
            seen_cols = set()
            for alias, info in alias_map.items():
                cols = self.completer.alias_resolver.resolve_columns(info, alias_map)
                table_name = info.get('name', '') if info['type'] == 'table' else ''
                type_map = {}
                if table_name:
                    detailed = self._fetch_table_columns_detailed(table_name)
                    type_map = {dc.name.upper(): dc.detail for dc in detailed}
                
                for c in cols:
                    if c.upper().startswith(last_token_upper):
                        col_type = type_map.get(c.upper(), '')
                        col_key = c.upper()
                        if col_key not in seen_cols:
                            seen_cols.add(col_key)
                            items.append(CompletionItem(
                                c, CompletionItem.TYPE_COLUMN,
                                detail=col_type
                            ))

            # 过滤掉表名（避免表名列名重复）
            conn_metadata = self._get_metadata()
            if conn_metadata:
                all_tables = set()
                for db_tables in conn_metadata.get('tables', {}).values():
                    for t in db_tables:
                        if isinstance(t, dict):
                            all_tables.add(t.get('name', '').upper())
                        else:
                            all_tables.add(t.upper())
                items = [item for item in items
                         if item.name.upper() not in all_tables or item.type == CompletionItem.TYPE_ALIAS]

        return items

    def _get_insert_col_completions(self, text_before_cursor, prefix):
        """获取 INSERT INTO 列补全"""
        items = []
        insert_match = re.search(r'INSERT\s+INTO\s+(\S+)', text_before_cursor, re.IGNORECASE)
        if not insert_match:
            return items
        table_name = insert_match.group(1)
        cols_with_type = self._fetch_table_columns_detailed(table_name)
        if cols_with_type:
            # 获取已写的列
            last_open = text_before_cursor.rfind('(')
            in_paren = text_before_cursor[last_open + 1:] if last_open >= 0 else ''
            existing_cols = set()
            for part in in_paren.split(','):
                part = part.strip()
                if part:
                    existing_cols.add(part.upper())
            for col_item in cols_with_type:
                if col_item.name.upper().startswith(prefix) and col_item.name.upper() not in existing_cols:
                    items.append(col_item)
        else:
            cols = self._fetch_table_columns(table_name)
            if cols:
                last_open = text_before_cursor.rfind('(')
                in_paren = text_before_cursor[last_open + 1:] if last_open >= 0 else ''
                existing_cols = set()
                for part in in_paren.split(','):
                    part = part.strip()
                    if part:
                        existing_cols.add(part.upper())
                for c in cols:
                    if c.upper().startswith(prefix) and c.upper() not in existing_cols:
                        items.append(CompletionItem(c, CompletionItem.TYPE_COLUMN))
        return items


# ================================================================
# 策略调度器
# ================================================================

class SQLCompleter:
    """
    SQL 智能补全器 - 策略模式调度器
    根据上下文自动选择合适的补全策略
    """

    def __init__(self, conn_id, conn_data=None, db_ops=None):
        self.conn_id = conn_id
        self.conn_data = conn_data
        self.db_ops = db_ops
        self.current_db = None
        self.cache = MetadataCache()

        # 初始化别名解析器
        self.alias_resolver = AliasResolver()

        # 初始化补全策略
        self._strategies = {
            'dot': DotCompletionStrategy(self),
            'context': ContextCompletionStrategy(self),
            'prefix': PrefixCompletionStrategy(self)
        }

    def get_completions(self, text_before_cursor, full_statement=None):
        """
        根据光标前的文本返回补全列表
        :param text_before_cursor: 语句开头到光标的文本
        :param full_statement: 完整 SQL 语句
        :return: 补全建议列表
        """
        if not text_before_cursor:
            return []

        full_statement = full_statement or text_before_cursor

        # 点号触发策略
        if text_before_cursor.endswith('.'):
            return self._strategies['dot'].get_completions(text_before_cursor, full_statement)

        # 提取最后一个 token
        tokens = re.split(r'[\s\n\(\),;]', text_before_cursor)
        last_token = tokens[-1] if tokens else ""

        if not last_token:
            # 无 token，触发上下文补全
            return self._strategies['context'].get_completions(text_before_cursor, full_statement)

        # 有 token，触发前缀匹配策略
        return self._strategies['prefix'].get_completions(text_before_cursor, full_statement)

    # ================================================================
    # 内部辅助方法 (供策略调用)
    # ================================================================

    def _fetch_table_columns(self, table_name):
        """从缓存或数据库获取表的列名"""
        conn_metadata = self._get_metadata()
        if conn_metadata:
            cols = self.cache.get_columns(self.conn_id, table_name)
            if cols:
                return cols
            for db_name in conn_metadata.get('tables', {}):
                cols = self.cache.get_columns(self.conn_id, f"{db_name}.{table_name}")
                if cols:
                    return cols

        if self.conn_data and self.db_ops:
            db = self.current_db or self.conn_data.get('database')
            return self.cache.fetch_columns_for_table(
                self.conn_id, self.conn_data, table_name, self.db_ops, database=db
            )
        return []

    def _fetch_table_columns_detailed(self, table_name):
        """从缓存或数据库获取表的列信息 (含类型) - 返回 CompletionItem 列表"""
        conn_metadata = self._get_metadata()
        cache = self.cache

        # 尝试从缓存获取详细列信息
        col_details = None
        if conn_metadata:
            col_details = cache.get_columns_detailed(self.conn_id, table_name)
            if not col_details:
                for db_name in conn_metadata.get('tables', {}):
                    col_details = cache.get_columns_detailed(self.conn_id, f"{db_name}.{table_name}")
                    if col_details:
                        break

        # 缓存没有，从数据库拉取
        if not col_details and self.conn_data and self.db_ops:
            db = self.current_db or self.conn_data.get('database')
            col_details_raw = cache.fetch_columns_for_table(
                self.conn_id, self.conn_data, table_name, self.db_ops, database=db
            )
            # fetch_columns_for_table 返回的是列名字符串列表
            # 再次获取详细列信息
            if conn_metadata:
                col_details = cache.get_columns_detailed(self.conn_id, table_name)
                if not col_details:
                    col_details = cache.get_columns_detailed(self.conn_id, f"{db}.{table_name}")

        if col_details:
            items = []
            for col in col_details:
                items.append(CompletionItem(
                    col['name'], CompletionItem.TYPE_COLUMN,
                    detail=col.get('type', '')
                ))
            return items

        return []

    def _get_metadata(self):
        """获取元数据缓存"""
        return self.cache.get_metadata(self.conn_id)