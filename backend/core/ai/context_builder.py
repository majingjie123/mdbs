"""AI 对话上下文构建器，提取数据库表结构并格式化为系统消息"""


class ContextBuilder:
    """构建 AI 对话所需的数据库表结构上下文"""

    @staticmethod
    def build_context(db_ops, conn_data, database, schema=None, table_names=None, progress_callback=None):
        """
        提取指定表的结构信息并格式化为文本
        :param db_ops: DBOperations 实例
        :param conn_data: 连接配置字典
        :param database: 数据库名
        :param schema: Schema 名（仅 PostgreSQL）
        :param table_names: 要包含的表名列表，None 表示全部
        :param progress_callback: 进度回调 progress_callback(current, total, table_name)
        :return: 格式化后的上下文文本
        """
        try:
            # 强制指定数据库
            conn_data_copy = conn_data.copy()
            conn_data_copy['database'] = database

            # 获取外键关系
            relations = []
            try:
                relations = db_ops.get_relations(conn_data_copy, database=database, schema=schema)
            except Exception:
                pass

            # 确定要获取的表名列表
            if table_names:
                target_tables = list(table_names)
            else:
                # 获取所有表名
                raw_tables = db_ops.get_tables(conn_data_copy, database=database, schema=schema)
                target_tables = [t['name'] if isinstance(t, dict) else t for t in raw_tables]

            if not target_tables:
                return "未找到任何表结构信息。"

            total = len(target_tables)

            # 逐表获取结构（支持进度回调）
            structures = {}
            for i, table_name in enumerate(target_tables):
                if progress_callback:
                    progress_callback(i + 1, total, table_name)
                try:
                    columns = db_ops.get_table_columns_detailed(
                        conn_data_copy, table_name, database=database, schema=schema
                    )
                    comment = ''
                    try:
                        options = db_ops.get_table_options_detailed(
                            conn_data_copy, table_name, database=database, schema=schema
                        )
                        if options:
                            comment = options.get('comment', '') or options.get('Comment', '')
                    except Exception:
                        pass
                    structures[table_name] = {'comment': comment, 'columns': columns}
                except Exception:
                    pass  # 单表获取失败不影响整体

            # 格式化表结构
            lines = []
            db_type = conn_data.get('db_type', 'MySQL')
            lines.append(f"数据库类型: {db_type}")
            lines.append(f"数据库名: {database}")
            if schema:
                lines.append(f"模式(Schema): {schema}")
            lines.append(f"\n以下是对话中涉及的 {len(structures)} 个表的结构信息：\n")

            for table_name, info in structures.items():
                comment = info.get('comment', '')
                comment_str = f" ({comment})" if comment else ""
                lines.append(f"表名: {table_name}{comment_str}")

                columns = info.get('columns', [])
                for col in columns:
                    col_line = ContextBuilder._format_column(col)
                    lines.append(f"  {col_line}")
                lines.append("")

            # 格式化外键关系
            if relations:
                relevant_relations = ContextBuilder._filter_relations(relations, structures.keys())
                if relevant_relations:
                    lines.append("外键关系:")
                    for rel in relevant_relations:
                        lines.append(f"  {rel}")
                    lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"构建上下文失败: {str(e)}"

    @staticmethod
    def _format_column(col):
        """格式化单列信息"""
        field = col.get('Field', '')
        col_type = col.get('Type', '')
        null = 'NOT NULL' if col.get('Null') == 'NO' else 'NULL'
        key = col.get('Key', '')
        default = col.get('Default')
        extra = col.get('Extra', '')
        comment = col.get('Comment', '')

        parts = [field, col_type, null]

        if key == 'PRI':
            parts.append('PRIMARY KEY')
        elif key == 'UNI':
            parts.append('UNIQUE')
        elif key == 'MUL':
            parts.append('INDEX')

        if default is not None:
            parts.append(f"DEFAULT '{default}'")

        if extra:
            parts.append(extra.upper())

        line = " ".join(parts)
        if comment:
            line += f" — {comment}"

        return f"- {line}"

    @staticmethod
    def _filter_relations(relations, table_names):
        """过滤只涉及选定表的外键关系"""
        result = []
        table_set = set(table_names)
        for rel in relations:
            # rel 通常是字典或字符串，取决于 db_operations 的返回格式
            if isinstance(rel, dict):
                from_table = rel.get('from_table', rel.get('table_name', ''))
                to_table = rel.get('to_table', rel.get('referenced_table_name', ''))
                from_col = rel.get('from_column', rel.get('column_name', ''))
                to_col = rel.get('to_column', rel.get('referenced_column_name', ''))
                constraint = rel.get('constraint', rel.get('fk_name', ''))

                # 检查是否涉及选定表（可能包含 schema 前缀）
                from_short = from_table.split('.')[-1] if from_table else ''
                to_short = to_table.split('.')[-1] if to_table else ''

                if from_short in table_set or to_short in table_set:
                    rel_str = f"{from_table}.{from_col} → {to_table}.{to_col}"
                    if constraint:
                        rel_str += f"  [{constraint}]"
                    result.append(rel_str)
            elif isinstance(rel, str):
                result.append(rel)
        return result
