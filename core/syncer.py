import threading
import time
import json
import os
import traceback
from datetime import datetime
import pymysql
import pg8000.native
from core.ssh_manager import SSHTunnelManager

class DatabaseSyncer:
    def __init__(self, source_conn_data, target_conn_data, options, progress_callback, cancel_event):
        """
        :param source_conn_data: 源连接配置 (已解密)
        :param target_conn_data: 目标连接配置 (已解密)
        :param options: 同步选项 {tables: [], sync_structure: bool, sync_data: bool, conflict_strategy: str}
        :param progress_callback: 回调函数 (event_type, data)
        :param cancel_event: threading.Event
        """
        self.source_data = source_conn_data
        self.target_data = target_conn_data
        self.options = options
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event
        
        self.ssh_manager = SSHTunnelManager()
        self.log_file = None
        self.log_path = ""
        
        # 统计信息
        self.stats = {
            'total_tables': len(options.get('tables', [])),
            'processed_tables': 0,
            'success_tables': 0,
            'failed_tables': 0,
            'total_rows': 0
        }

    def _log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        if self.log_file:
            self.log_file.write(log_entry)
            self.log_file.flush()
        self.progress_callback("log", {"message": log_entry, "level": level})

    def run(self):
        """同步主入口"""
        # 创建日志文件
        log_dir = "sync_logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.log_path = os.path.join(log_dir, f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        
        self._log(f"开始同步任务: {self.source_data['name']} -> {self.target_data['name']}")
        
        source_conn = None
        target_conn = None
        
        try:
            # 1. 建立连接 (含 SSH)
            self._log("正在连接源数据库...")
            source_conn = self._get_connection(self.source_data)
            self._log("源数据库连接成功")
            
            self._log("正在连接目标数据库...")
            target_conn = self._get_connection(self.target_data)
            self._log("目标数据库连接成功")
            
            # 2. 循环处理每个表
            tables = self.options.get('tables', [])
            for table in tables:
                if self.cancel_event.is_set():
                    self._log("任务被用户取消", "WARNING")
                    break
                
                self.stats['processed_tables'] += 1
                self.progress_callback("progress", {
                    "table": table, 
                    "index": self.stats['processed_tables'], 
                    "total": self.stats['total_tables'],
                    "percent": int(self.stats['processed_tables'] / self.stats['total_tables'] * 100)
                })
                
                try:
                    self._sync_table(source_conn, target_conn, table)
                    self.stats['success_tables'] += 1
                except Exception as e:
                    self.stats['failed_tables'] += 1
                    self._log(f"同步表 {table} 失败: {str(e)}", "ERROR")
                    self._log(traceback.format_exc(), "DEBUG")

            self._log("同步任务结束")
            self._log(f"总计: {self.stats['total_tables']}, 成功: {self.stats['success_tables']}, 失败: {self.stats['failed_tables']}")
            
            status = "success" if self.stats['failed_tables'] == 0 else "partial"
            if self.stats['processed_tables'] == 0: status = "failed"
            
            self.progress_callback("done", {
                "status": status,
                "log_path": self.log_path,
                "stats": self.stats
            })

        except Exception as e:
            self._log(f"同步任务发生严重错误: {str(e)}", "ERROR")
            self._log(traceback.format_exc(), "DEBUG")
            self.progress_callback("done", {
                "status": "failed",
                "log_path": self.log_path,
                "error": str(e)
            })
        finally:
            if source_conn: self._close_connection(source_conn, self.source_data)
            if target_conn: self._close_connection(target_conn, self.target_data)
            if self.log_file: self.log_file.close()

    def _get_connection(self, conn_data):
        db_type = conn_data.get('db_type', 'MySQL')
        host = conn_data['host']
        port = int(conn_data['port'])
        
        if conn_data.get('ssh_enabled'):
            host, port = self.ssh_manager.start_tunnel(conn_data)
            
        if db_type == "MySQL":
            # 开启自动重连、增加超时到 60s
            return pymysql.connect(
                host=host, port=port,
                user=conn_data['user'], password=conn_data.get('password'),
                database=conn_data.get('database'),
                connect_timeout=60, charset='utf8mb4',
                autocommit=True, # 同步时实时提交
                cursorclass=pymysql.cursors.DictCursor
            )
        else:
            return pg8000.native.Connection(
                user=conn_data['user'], password=conn_data.get('password'),
                host=host, port=port,
                database=conn_data.get('database'),
                timeout=60
            )

    def _close_connection(self, conn, conn_data):
        try:
            if hasattr(conn, 'close'):
                conn.close()
        except:
            pass

    def _sync_table(self, source_conn, target_conn, table_name):
        self._log(f"正在处理表: {table_name}")
        
        # 1. 结构同步
        if self.options.get('sync_structure'):
            self._log(f"正在同步表结构: {table_name}")
            # 保活：同步结构前先 ping 一下连接
            db_type = self.source_data.get('db_type', 'MySQL')
            if db_type == "MySQL":
                source_conn.ping(reconnect=True)
            target_conn.ping(reconnect=True)
            ddl = self._get_create_statement(source_conn, table_name)
            self._apply_ddl(target_conn, table_name, ddl)
            self._log(f"表结构同步完成: {table_name}")

        # 2. 数据同步
        if self.options.get('sync_data'):
            self._log(f"正在同步数据: {table_name}")
            
            # 保活：开始前先 ping 一下连接
            db_type = self.source_data.get('db_type', 'MySQL')
            if db_type == "MySQL":
                source_conn.ping(reconnect=True)
                target_conn.ping(reconnect=True)

            self._sync_table_data(source_conn, target_conn, table_name)
            self._log(f"表数据同步完成: {table_name}")

    def _get_create_statement(self, conn, table_name):
        db_type = self.source_data.get('db_type', 'MySQL')
        if db_type == "MySQL":
            with conn.cursor() as cursor:
                cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                res = cursor.fetchone()
                return res.get('Create Table') or list(res.values())[1]
        else:
            # 获取表所在 schema
            schema = self.source_data.get('schema', 'public')

            # 获取列信息
            cols_res = conn.run(f"""
                SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale,
                       is_nullable, column_default, ordinal_position
                FROM information_schema.columns
                WHERE table_name = '{table_name}' AND table_schema = '{schema}'
                ORDER BY ordinal_position
            """)

            # 获取主键信息
            pk_res = conn.run(f"""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = '{table_name}'::regclass AND i.indisprimary
            """)
            pk_columns = [r[0] for r in pk_res]

            col_defs = []
            for c in cols_res:
                col_name = c[0]
                data_type = c[1]
                char_len = c[2]
                numeric_prec = c[3]
                numeric_scale = c[4]
                is_nullable = c[5]
                column_default = c[6]

                # 构建数据类型字符串
                if data_type in ('character varying', 'varchar'):
                    dtype = f"VARCHAR({char_len})" if char_len else "VARCHAR"
                elif data_type in ('character', 'char'):
                    dtype = f"CHAR({char_len})" if char_len else "CHAR"
                elif data_type in ('numeric', 'decimal'):
                    if numeric_prec:
                        dtype = f"NUMERIC({numeric_prec},{numeric_scale})" if numeric_scale is not None else f"NUMERIC({numeric_prec})"
                    else:
                        dtype = "NUMERIC"
                elif data_type == 'integer' and col_name in pk_columns:
                    dtype = "SERIAL"
                else:
                    dtype = data_type.upper()

                # NOT NULL
                null_str = "NOT NULL" if is_nullable == 'NO' else ""

                # DEFAULT
                def_str = f"DEFAULT {column_default}" if column_default else ""

                col_defs.append(f'    "{col_name}" {dtype} {null_str} {def_str}'.strip())

            # 添加主键约束
            if pk_columns:
                col_defs.append(f'    PRIMARY KEY ({", ".join(pk_columns)})')

            return f'CREATE TABLE "{table_name}" (\n  ' + ",\n  ".join(col_defs) + "\n)"

    def _apply_ddl(self, conn, table_name, ddl):
        db_type = self.target_data.get('db_type', 'MySQL')
        conflict_strategy = self.options.get('conflict_strategy', 'overwrite')
        
        if db_type == "MySQL":
            with conn.cursor() as cursor:
                if conflict_strategy == "overwrite":
                    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                cursor.execute(ddl)
        else:
            if conflict_strategy == "overwrite":
                conn.run(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.run(ddl)

    def _sync_table_data(self, source_conn, target_conn, table_name):
        db_type = self.source_data.get('db_type', 'MySQL')
        
        if db_type == "MySQL":
            # 针对 MySQL 大表使用流式游标，防止 OOM 并维持长连接
            from pymysql.cursors import SSDictCursor
            with source_conn.cursor(SSDictCursor) as cursor:
                cursor.execute(f"SELECT * FROM `{table_name}`")
                columns = None
                batch = []
                for row in cursor:
                    if self.cancel_event.is_set(): break
                    if not columns: columns = row.keys()
                    batch.append(row)
                    if len(batch) >= 1000:
                        self._batch_insert(target_conn, table_name, columns, batch)
                        batch = []
                if batch:
                    self._batch_insert(target_conn, table_name, columns, batch)
        else:
            res = source_conn.run(f'SELECT * FROM "{table_name}"')
            if not res: return
            cols_info = source_conn.run(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' ORDER BY ordinal_position")
            columns = [c[0] for c in cols_info]
            self._batch_insert(target_conn, table_name, columns, res)

    def _batch_insert(self, conn, table_name, columns, rows, batch_size=1000):
        db_type = self.target_data.get('db_type', 'MySQL')

        if db_type == "MySQL":
            cols_str = ", ".join([f"`{c}`" for c in columns])
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})"

            with conn.cursor() as cursor:
                data = []
                for row in rows:
                    if self.cancel_event.is_set(): break
                    data.append(tuple(row[c] for c in columns))
                    if len(data) >= batch_size:
                        cursor.executemany(sql, data)
                        data = []
                if data:
                    cursor.executemany(sql, data)
            conn.commit()  # 显式提交确保数据写入
        elif db_type == "PostgreSQL":
            cols_str = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join([f":{i}" for i in range(len(columns))])
            sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'

            data_batch = []
            for row in rows:
                if self.cancel_event.is_set(): break
                data_batch.append(row)
                if len(data_batch) >= batch_size:
                    for r in data_batch:
                        conn.run(sql, **dict(zip([f":{i}" for i in range(len(columns))], r)))
                    data_batch = []
            if data_batch:
                for r in data_batch:
                    conn.run(sql, **dict(zip([f":{i}" for i in range(len(columns))], r)))
