import threading
from core.db_operations import DBOperations

class MetadataCache:
    _instance = None
    # 缓存结构: {conn_id: {'dbs': [], 'tables': {db: [table_info, ...]}, 'columns': {key: [col_info, ...]}}}
    # table_info: {'name': str, 'comment': str}
    # col_info: {'name': str, 'comment': str}
    _cache = {}
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MetadataCache, cls).__new__(cls)
        return cls._instance

    def get_metadata(self, conn_id):
        return self._cache.get(conn_id)

    def refresh(self, conn_id, conn_data, db_ops):
        """后台异步刷新元数据"""
        def _task():
            try:
                metadata = {'dbs': [], 'tables': {}, 'columns': {}}
                dbs = db_ops.get_databases(conn_data)
                metadata['dbs'] = dbs

                current_db = conn_data.get('database')
                if current_db:
                    tables = db_ops.get_tables(conn_data, database=current_db)
                    metadata['tables'][current_db] = tables

                with self._lock:
                    self._cache[conn_id] = metadata
            except Exception as e:
                print(f"元数据缓存刷新失败: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def get_tables(self, conn_id, db_name):
        """获取表名列表 (仅名称)"""
        conn_cache = self._cache.get(conn_id)
        if conn_cache:
            tables = conn_cache['tables'].get(db_name, [])
            return [t['name'] if isinstance(t, dict) else t for t in tables]
        return []

    def get_table_comment(self, conn_id, db_name, table_name):
        """获取表备注"""
        conn_cache = self._cache.get(conn_id)
        if conn_cache:
            tables = conn_cache['tables'].get(db_name, [])
            for t in tables:
                if isinstance(t, dict) and t.get('name') == table_name:
                    return t.get('comment', '')
        return ''

    def get_dbs(self, conn_id):
        conn_cache = self._cache.get(conn_id)
        if conn_cache:
            return conn_cache['dbs']
        return []

    def get_columns(self, conn_id, table_key):
        """获取已缓存的列名列表，table_key 为 'db.table' 或 'table'"""
        conn_cache = self._cache.get(conn_id)
        if conn_cache:
            cols = conn_cache.get('columns', {}).get(table_key, [])
            return [c['name'] if isinstance(c, dict) else c for c in cols]
        return []

    def get_column_comment(self, conn_id, table_key, column_name):
        """获取列备注"""
        conn_cache = self._cache.get(conn_id)
        if conn_cache:
            cols = conn_cache.get('columns', {}).get(table_key, [])
            for c in cols:
                if isinstance(c, dict) and c.get('name') == column_name:
                    return c.get('comment', '')
        return ''

    def get_columns_detailed(self, conn_id, table_key):
        """获取已缓存的列详细信息（含 type, comment），table_key 为 'db.table' 或 'table'"""
        conn_cache = self._cache.get(conn_id)
        if conn_cache:
            cols = conn_cache.get('columns', {}).get(table_key, [])
            if cols and isinstance(cols[0], dict):
                return cols
            return []
        return []

    def fetch_tables_for_db(self, conn_id, conn_data, db_name, db_ops, schema=None, callback=None):
        """为指定数据库/模式异步拉取表列表 (包含备注)"""
        def _task():
            try:
                tables = db_ops.get_tables(conn_data, database=db_name, schema=schema)
                cache_key = f"{db_name}.{schema}" if schema else db_name

                with self._lock:
                    if conn_id not in self._cache:
                        self._cache[conn_id] = {'dbs': [], 'tables': {}, 'columns': {}}
                    self._cache[conn_id]['tables'][cache_key] = tables

                if callback:
                    callback()
            except Exception as e:
                print(f"异步拉取表失败 ({db_name}.{schema if schema else ''}): {e}")

        threading.Thread(target=_task, daemon=True).start()

    def fetch_columns_for_table(self, conn_id, conn_data, table_name, db_ops, database=None, schema=None):
        """同步拉取并缓存指定表的列信息 (包含备注)"""
        cache_key = f"{database}.{table_name}" if database else table_name

        cached = self.get_columns(conn_id, cache_key)
        if cached:
            return cached

        try:
            db = database or conn_data.get('database')
            rows = db_ops.get_table_columns_detailed(conn_data, table_name, database=db, schema=schema)
            col_names = [row['Field'] for row in rows] if rows else []

            # 存储详细信息 (包含备注)
            cols_with_comment = []
            for row in rows:
                cols_with_comment.append({
                    'name': row['Field'],
                    'type': row.get('Type', ''),
                    'comment': row.get('Comment', '') or row.get('comment', '')
                })

            with self._lock:
                if conn_id not in self._cache:
                    self._cache[conn_id] = {'dbs': [], 'tables': {}, 'columns': {}}
                self._cache[conn_id]['columns'][cache_key] = cols_with_comment

            return col_names
        except Exception as e:
            print(f"拉取列信息失败 ({cache_key}, db={database}): {e}")
            return []
