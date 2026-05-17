import sqlite3
import os
import json
from datetime import datetime
from utils.crypto import CryptoUtils

class DBStorage:
    _db_path = "connections.db"

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构并执行平滑迁移"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            # 1. 创建基础表 (如果不存在)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    user TEXT NOT NULL,
                    password TEXT,
                    database TEXT,
                    ssh_enabled INTEGER DEFAULT 0,
                    ssh_host TEXT,
                    ssh_port INTEGER DEFAULT 22,
                    ssh_user TEXT,
                    ssh_auth_type TEXT,
                    ssh_password TEXT,
                    ssh_key_path TEXT,
                    ssh_key_phrase TEXT,
                    ssh_local_port INTEGER,
                    ssh_remote_host TEXT,
                    ssh_remote_port INTEGER
                )
            ''')
            
            # 2. 检查并添加缺失的列 (自动迁移)
            cursor.execute("PRAGMA table_info(connections)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # 迁移 1: 增加 db_type 列
            if 'db_type' not in columns:
                cursor.execute("ALTER TABLE connections ADD COLUMN db_type TEXT DEFAULT 'MySQL'")

            # 3. 创建设置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # 4. 创建同步历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    source_conn_id INTEGER NOT NULL,
                    source_db TEXT NOT NULL,
                    target_conn_id INTEGER NOT NULL,
                    target_db TEXT NOT NULL,
                    tables TEXT,                 -- JSON 数组
                    sync_structure INTEGER DEFAULT 0,
                    sync_data INTEGER DEFAULT 0,
                    status TEXT CHECK(status IN ('success', 'partial', 'failed', 'running')),
                    log_path TEXT,
                    error_summary TEXT
                )
            ''')
            
            # 5. 创建 SQL 执行历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sql_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conn_id INTEGER NOT NULL,
                    execution_time TEXT NOT NULL,
                    sql_text TEXT NOT NULL,
                    status TEXT CHECK(status IN ('success', 'failed')),
                    rows_affected INTEGER DEFAULT 0,
                    error_msg TEXT
                )
            ''')
            
            # 6. 创建工作台完整日志表 (用于持久化显示，与脚本路径绑定)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workbench_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_path TEXT NOT NULL UNIQUE,
                    log_content TEXT,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 迁移 2: 检查 workbench_logs 是否需要从 (conn_name, db_name) 迁移到 script_path
            cursor.execute("PRAGMA table_info(workbench_logs)")
            wb_columns = [row[1] for row in cursor.fetchall()]
            if 'script_path' not in wb_columns:
                # 这是一个破坏性变更或需要重新定义的表，为保持简单，如果数据不重要可以重建，
                # 但这里我们采用更安全的 ALTER TABLE + 降级处理
                cursor.execute("ALTER TABLE workbench_logs ADD COLUMN script_path TEXT")
                # 如果旧列存在，尝试通过 conn_name 和 db_name 拼凑一个临时的 script_path (虽然不一定准确，但能防止崩溃)
                if 'conn_name' in wb_columns and 'db_name' in wb_columns:
                    cursor.execute("UPDATE workbench_logs SET script_path = 'legacy_' || conn_name || '_' || db_name WHERE script_path IS NULL")
            
            # 7. 创建 AI 配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    protocol TEXT DEFAULT 'openai',
                    api_key TEXT,
                    base_url TEXT DEFAULT 'https://api.openai.com/v1',
                    model TEXT DEFAULT 'gpt-3.5-turbo',
                    system_prompt TEXT,
                    temperature REAL DEFAULT 0.7,
                    max_tokens INTEGER DEFAULT 2048,
                    is_default INTEGER DEFAULT 0
                )
            ''')

            # 8. 创建 AI 聊天历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conn_id INTEGER,
                    db_name TEXT,
                    script_path TEXT,
                    messages TEXT,
                    context_summary TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

            # 平滑迁移：为 ai_chat_history 添加 context_text 列
            try:
                cursor.execute('ALTER TABLE ai_chat_history ADD COLUMN context_text TEXT')
            except sqlite3.OperationalError:
                pass  # 列已存在

            conn.commit()

    def save_workbench_log(self, script_path, content):
        """持久化保存工作台的所有日志文本，按脚本路径绑定"""
        if not script_path: return
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('''
                INSERT INTO workbench_logs (script_path, log_content, update_time)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(script_path) DO UPDATE SET 
                    log_content = excluded.log_content,
                    update_time = CURRENT_TIMESTAMP
            ''', (script_path, content))
            conn.commit()

    def get_workbench_log(self, script_path):
        """读取持久化的工作台日志"""
        if not script_path: return ""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute('SELECT log_content FROM workbench_logs WHERE script_path = ?', (script_path,)).fetchone()
            return row[0] if row else ""

    def delete_workbench_log(self, script_path):
        """删除特定脚本对应的日志"""
        if not script_path: return
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('DELETE FROM workbench_logs WHERE script_path = ?', (script_path,))
            conn.commit()

    def add_sql_history(self, history_data):
        """保存 SQL 执行历史"""
        query = '''
            INSERT INTO sql_history (conn_id, execution_time, sql_text, status, rows_affected, error_msg)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        params = (
            history_data['conn_id'],
            history_data['execution_time'],
            history_data['sql_text'],
            history_data['status'],
            history_data.get('rows_affected', 0),
            history_data.get('error_msg')
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(query, params)
            conn.commit()

    def get_sql_history(self, conn_id=None, limit=100):
        """获取 SQL 执行历史"""
        query = 'SELECT * FROM sql_history'
        params = []
        if conn_id:
            query += ' WHERE conn_id = ?'
            params.append(conn_id)
        query += ' ORDER BY execution_time DESC LIMIT ?'
        params.append(limit)
        
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def clear_sql_history(self, conn_id=None):
        """清空历史"""
        query = 'DELETE FROM sql_history'
        params = []
        if conn_id:
            query += ' WHERE conn_id = ?'
            params.append(conn_id)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(query, params)
            conn.commit()

    def get_settings(self):
        """获取所有设置项"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM settings')
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    def save_settings(self, settings_dict):
        """保存设置项"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            for key, value in settings_dict.items():
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
            conn.commit()

    def save_geometry(self, name, geometry):
        """保存窗口位置和大小"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (f"geometry_{name}", geometry))
            conn.commit()

    def get_geometry(self, name):
        """获取窗口位置和大小"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute('SELECT value FROM settings WHERE key = ?', (f"geometry_{name}",)).fetchone()
            return row[0] if row else None

    def add_connection(self, data):
        """添加连接，对密码进行加密"""
        encrypted_data = self._process_passwords(data, encrypt=True)
        query = '''
            INSERT INTO connections (
                db_type, name, host, port, user, password, database,
                ssh_enabled, ssh_host, ssh_port, ssh_user, ssh_auth_type,
                ssh_password, ssh_key_path, ssh_key_phrase, ssh_local_port,
                ssh_remote_host, ssh_remote_port
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            encrypted_data.get('db_type', 'MySQL'),
            encrypted_data['name'], encrypted_data['host'], encrypted_data['port'], 
            encrypted_data['user'], encrypted_data['password'], encrypted_data['database'],
            encrypted_data.get('ssh_enabled', 0), encrypted_data.get('ssh_host'), 
            encrypted_data.get('ssh_port', 22), encrypted_data.get('ssh_user'),
            encrypted_data.get('ssh_auth_type'), encrypted_data.get('ssh_password'),
            encrypted_data.get('ssh_key_path'), encrypted_data.get('ssh_key_phrase'),
            encrypted_data.get('ssh_local_port'), encrypted_data.get('ssh_remote_host'),
            encrypted_data.get('ssh_remote_port')
        )
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def update_connection(self, conn_id, data):
        """更新连接"""
        encrypted_data = self._process_passwords(data, encrypt=True)
        query = '''
            UPDATE connections SET 
                db_type=?, name=?, host=?, port=?, user=?, password=?, database=?,
                ssh_enabled=?, ssh_host=?, ssh_port=?, ssh_user=?, ssh_auth_type=?,
                ssh_password=?, ssh_key_path=?, ssh_key_phrase=?, ssh_local_port=?,
                ssh_remote_host=?, ssh_remote_port=?
            WHERE id=?
        '''
        params = (
            encrypted_data.get('db_type', 'MySQL'),
            encrypted_data['name'], encrypted_data['host'], encrypted_data['port'], 
            encrypted_data['user'], encrypted_data['password'], encrypted_data['database'],
            encrypted_data.get('ssh_enabled', 0), encrypted_data.get('ssh_host'), 
            encrypted_data.get('ssh_port', 22), encrypted_data.get('ssh_user'),
            encrypted_data.get('ssh_auth_type'), encrypted_data.get('ssh_password'),
            encrypted_data.get('ssh_key_path'), encrypted_data.get('ssh_key_phrase'),
            encrypted_data.get('ssh_local_port'), encrypted_data.get('ssh_remote_host'),
            encrypted_data.get('ssh_remote_port'),
            conn_id
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(query, params)
            conn.commit()

    def delete_connection(self, conn_id):
        """删除连接"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('DELETE FROM connections WHERE id=?', (conn_id,))
            conn.commit()

    def get_all_connections(self):
        """获取所有连接，并解密密码"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM connections')
            rows = cursor.fetchall()
            return [self._process_passwords(dict(row), encrypt=False) for row in rows]

    def get_connection(self, conn_id):
        """获取单个连接"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM connections WHERE id=?', (conn_id,))
            row = cursor.fetchone()
            if row:
                return self._process_passwords(dict(row), encrypt=False)
            return None

    def _process_passwords(self, data, encrypt=True):
        """统一处理数据中的敏感字段加密/解密"""
        fields = ['password', 'ssh_password', 'ssh_key_phrase']
        processed = data.copy()
        for field in fields:
            if field in processed and processed[field]:
                if encrypt:
                    processed[field] = CryptoUtils.encrypt(processed[field])
                else:
                    processed[field] = CryptoUtils.decrypt(processed[field])
        return processed

    # ---- AI 配置管理 ----

    def get_ai_configs(self):
        """获取所有 AI 配置，解密 api_key"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ai_configs ORDER BY is_default DESC, name')
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                if d.get('api_key'):
                    d['api_key'] = CryptoUtils.decrypt(d['api_key'])
                result.append(d)
            return result

    def get_ai_config(self, config_id):
        """获取单个 AI 配置"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM ai_configs WHERE id=?', (config_id,)).fetchone()
            if row:
                d = dict(row)
                if d.get('api_key'):
                    d['api_key'] = CryptoUtils.decrypt(d['api_key'])
                return d
            return None

    def get_default_ai_config(self):
        """获取默认 AI 配置"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM ai_configs WHERE is_default=1').fetchone()
            if row:
                d = dict(row)
                if d.get('api_key'):
                    d['api_key'] = CryptoUtils.decrypt(d['api_key'])
                return d
            # 没有默认配置则返回第一个
            row = conn.execute('SELECT * FROM ai_configs ORDER BY id LIMIT 1').fetchone()
            if row:
                d = dict(row)
                if d.get('api_key'):
                    d['api_key'] = CryptoUtils.decrypt(d['api_key'])
                return d
            return None

    def save_ai_config(self, data):
        """新增或更新 AI 配置，加密 api_key"""
        processed = data.copy()
        if processed.get('api_key'):
            processed['api_key'] = CryptoUtils.encrypt(processed['api_key'])

        if processed.get('id'):
            # 更新
            config_id = processed.pop('id')
            # 如果设为默认，先取消其他默认
            if processed.get('is_default'):
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute('UPDATE ai_configs SET is_default=0')
                    conn.commit()
            sets = ', '.join(f'{k}=?' for k in processed.keys())
            params = list(processed.values()) + [config_id]
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(f'UPDATE ai_configs SET {sets} WHERE id=?', params)
                conn.commit()
            return config_id
        else:
            # 新增
            processed.pop('id', None)
            if processed.get('is_default'):
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute('UPDATE ai_configs SET is_default=0')
                    conn.commit()
            cols = ', '.join(processed.keys())
            placeholders = ', '.join('?' for _ in processed)
            params = list(processed.values())
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'INSERT INTO ai_configs ({cols}) VALUES ({placeholders})', params)
                conn.commit()
                return cursor.lastrowid

    def delete_ai_config(self, config_id):
        """删除 AI 配置"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('DELETE FROM ai_configs WHERE id=?', (config_id,))
            conn.commit()

    # ---- AI 聊天历史 ----

    def save_chat_history(self, conn_id, db_name, script_path, messages, context_summary='', context_text=''):
        """保存 AI 聊天历史"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        messages_json = json.dumps(messages, ensure_ascii=False) if isinstance(messages, list) else messages
        with sqlite3.connect(self._db_path) as conn:
            # 查找已有记录
            row = conn.execute(
                'SELECT id FROM ai_chat_history WHERE conn_id=? AND db_name=? AND script_path=?',
                (conn_id, db_name, script_path)
            ).fetchone()
            if row:
                conn.execute('''
                    UPDATE ai_chat_history SET messages=?, context_summary=?, context_text=?, updated_at=?
                    WHERE id=?
                ''', (messages_json, context_summary, context_text, now, row[0]))
            else:
                conn.execute('''
                    INSERT INTO ai_chat_history (conn_id, db_name, script_path, messages, context_summary, context_text, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (conn_id, db_name, script_path, messages_json, context_summary, context_text, now, now))
            conn.commit()

    def get_chat_history(self, conn_id, db_name, script_path):
        """读取 AI 聊天历史"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                'SELECT messages, context_summary, context_text FROM ai_chat_history WHERE conn_id=? AND db_name=? AND script_path=?',
                (conn_id, db_name, script_path)
            ).fetchone()
            if row:
                messages = json.loads(row[0]) if row[0] else []
                return messages, row[1] or '', row[2] or ''
            return [], '', ''

    def delete_chat_history(self, conn_id=None, db_name=None, script_path=None):
        """删除 AI 聊天历史"""
        with sqlite3.connect(self._db_path) as conn:
            if script_path:
                conn.execute('DELETE FROM ai_chat_history WHERE script_path=?', (script_path,))
            elif conn_id and db_name:
                conn.execute('DELETE FROM ai_chat_history WHERE conn_id=? AND db_name=?', (conn_id, db_name))
            elif conn_id:
                conn.execute('DELETE FROM ai_chat_history WHERE conn_id=?', (conn_id,))
            else:
                conn.execute('DELETE FROM ai_chat_history')
            conn.commit()

    def migrate_chat_history(self, old_path, new_path):
        """迁移聊天历史（用于脚本保存/重命名）"""
        if not old_path or not new_path or old_path == new_path:
            return
        with sqlite3.connect(self._db_path) as conn:
            # 检查目标路径是否已有历史，如果有则合并或替换（这里选择替换以保证一致性）
            conn.execute('DELETE FROM ai_chat_history WHERE script_path = ?', (new_path,))
            conn.execute('UPDATE ai_chat_history SET script_path = ? WHERE script_path = ?', (new_path, old_path))
            conn.commit()
