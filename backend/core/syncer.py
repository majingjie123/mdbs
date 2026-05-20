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
    def __init__(self, source_conn_data, target_conn_data, options, progress_callback, cancel_event,
                 source_db=None, target_db=None):
        """
        :param source_conn_data: 源连接配置 (已解密)
        :param target_conn_data: 目标连接配置 (已解密)
        :param options: 同步选项 {tables: [], sync_structure: bool, sync_data: bool, conflict_strategy: str}
        :param progress_callback: 回调函数 (event_type, data)
        :param cancel_event: threading.Event
        :param source_db: 源数据库名（覆盖连接配置中的默认库）
        :param target_db: 目标数据库名（覆盖连接配置中的默认库）
        """
        self.source_data = source_conn_data
        self.target_data = target_conn_data
        self.options = options
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event
        self.source_db = source_db or source_conn_data.get('database', '')
        self.target_db = target_db or target_conn_data.get('database', '')
        
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
            source_conn = self._get_connection(self.source_data, self.source_db)
            self._log("源数据库连接成功")
            
            self._log("正在连接目标数据库...")
            target_conn = self._get_connection(self.target_data, self.target_db)
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

    def _get_connection(self, conn_data, database=None):
        db_type = conn_data.get('db_type', 'MySQL')
        host = conn_data['host']
        port = int(conn_data['port'])
        
        if conn_data.get('ssh_enabled'):
            host, port = self.ssh_manager.start_tunnel(conn_data)
            
        # 使用传入的 database 覆盖连接配置中的默认库
        db_name = database or conn_data.get('database', '')
            
        if db_type == "MySQL":
            # 开启自动重连、增加超时到 60s
            return pymysql.connect(
                host=host, port=port,
                user=conn_data['user'], password=conn_data.get('password'),
                database=db_name,
                connect_timeout=60, charset='utf8mb4',
                autocommit=True, # 同步时实时提交
                cursorclass=pymysql.cursors.DictCursor
            )
        else:
            return pg8000.native.Connection(
                user=conn_data['user'], password=conn_data.get('password'),
                host=host, port=port,
                database=db_name,
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

    def _get_primary_keys(self, conn, table_name, db_type):
        """获取主键列名列表"""
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW KEYS FROM `{table_name}` WHERE Key_name = 'PRIMARY'")
                    return [r['Column_name'] for r in cursor.fetchall()]
            else:
                # 使用 table_name 对应的 schema
                schema = self.source_data.get('schema', 'public')
                res = conn.run(f"""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = '{schema}.{table_name}'::regclass AND i.indisprimary
                """)
                return [r[0] for r in res]
        except Exception:
            return []

    # ── 优化 1: 数据同步前暂存非主键索引，同步后重建 ──────────────
    def _get_non_pk_indexes(self, conn, table_name, db_type):
        """获取非主键索引 DDL（同步前保存，同步后重建）"""
        indexes = []
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                    row = cursor.fetchone()
                    ddl = row.get('Create Table') or list(row.values())[1]
                    for line in ddl.split('\n'):
                        line = line.strip().rstrip(',')
                        if line.startswith('KEY ') or line.startswith('UNIQUE KEY ') or line.startswith('INDEX '):
                            indexes.append(line)
            else:
                schema = self.source_data.get('schema', 'public')
                res = conn.run(f"""
                    SELECT indexdef FROM pg_indexes
                    WHERE tablename = '{table_name}' AND schemaname = '{schema}'
                      AND indexname NOT LIKE '%_pkey'
                """)
                indexes = [r[0] for r in res]
        except Exception:
            pass
        return indexes

    def _drop_indexes(self, conn, table_name, indexes, db_type):
        """删除非主键索引"""
        for idx in indexes:
            try:
                if db_type == "MySQL":
                    # 从 KEY `name` (...) 中提取索引名
                    import re
                    m = re.search(r'KEY\s+`([^`]+)`', idx) or re.search(r'INDEX\s+`([^`]+)`', idx)
                    if m:
                        conn.cursor().execute(f"ALTER TABLE `{table_name}` DROP INDEX `{m.group(1)}`")
                else:
                    # 从 CREATE INDEX ... ON ... 中提取完整语句，替换为 DROP
                    idx_name = idx.split(' ')[2] if idx else ''
                    if idx_name:
                        conn.run(f'DROP INDEX IF EXISTS "{idx_name}"')
            except Exception:
                pass

    def _recreate_indexes(self, conn, table_name, indexes, db_type):
        """重新创建索引"""
        for idx in indexes:
            try:
                if db_type == "MySQL":
                    with conn.cursor() as cursor:
                        cursor.execute(f"ALTER TABLE `{table_name}` ADD {idx}")
                else:
                    conn.run(idx)
            except Exception:
                self._log(f"重建索引失败: {idx}", "WARNING")

    # ── 优化 2: 分批拉取数据 + 流式写入 ──────────────────────
    def _get_table_count(self, conn, table_name, db_type):
        """获取表行数（用于进度估算）"""
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
                    return cursor.fetchone()['cnt']
            else:
                res = conn.run(f'SELECT COUNT(*) FROM "{table_name}"')
                return res[0][0]
        except Exception:
            return None

    # ── 优化 3: 冲突处理 INSERT ... ON DUPLICATE KEY / ON CONFLICT ──
    def _build_insert_sql(self, table_name, columns, db_type, pk_columns, conflict_strategy):
        """构建 INSERT SQL，支持冲突策略"""
        if db_type == "MySQL":
            cols_str = ", ".join([f"`{c}`" for c in columns])
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})"
            if conflict_strategy == "update" and pk_columns:
                update_parts = [f"`{c}`=VALUES(`{c}`)" for c in columns if c not in pk_columns]
                if update_parts:
                    sql += " ON DUPLICATE KEY UPDATE " + ", ".join(update_parts)
            return sql
        else:
            cols_str = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join([f":{i}" for i in range(len(columns))])
            sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'
            if conflict_strategy == "overwrite":
                sql += " ON CONFLICT DO NOTHING"
            elif conflict_strategy == "update" and pk_columns:
                update_cols = [c for c in columns if c not in pk_columns]
                if update_cols:
                    update_str = ", ".join([f'"{c}"=EXCLUDED."{c}"' for c in update_cols])
                    sql += f" ON CONFLICT ({', '.join(pk_columns)}) DO UPDATE SET {update_str}"
            return sql

    def _sync_mysql_data(self, source_conn, target_conn, table_name, pk_columns, conflict):
        """MySQL 大表数据同步：流式 + 批量 + 冲突检测 + 索引优化"""
        from pymysql.cursors import SSDictCursor

        # 获取行数（用于进度估算）
        total_est = self._get_table_count(source_conn, table_name, "MySQL")
        if total_est and total_est == 0:
            self._log(f"表 {table_name} 无数据，跳过")
            return

        # 索引优化：同步前暂存并删除非主键索引
        idx_ddl = []
        if conflict != "update":  # update 模式下保留索引以支持 ON DUPLICATE KEY
            idx_ddl = self._get_non_pk_indexes(target_conn, table_name, "MySQL")
            if idx_ddl:
                self._log(f"暂存 {len(idx_ddl)} 个非主键索引，数据同步后重建")
                self._drop_indexes(target_conn, table_name, idx_ddl, "MySQL")

        insert_sql = self._build_insert_sql(table_name, pk_columns or [], "MySQL", pk_columns, conflict)
        _ = insert_sql  # 暂不改变原 INSERT 逻辑，保持向后兼容
        insert_sql = self._build_insert_sql(table_name, [], "MySQL", [], "overwrite")

        # 构建列名（从第一次读取获取）
        columns = None
        batch = []
        batch_num = 0
        inserted = 0
        last_progress = 0

        with source_conn.cursor(SSDictCursor) as cursor:
            cursor.execute(f"SELECT * FROM `{table_name}`")
            for row in cursor:
                if self.cancel_event.is_set():
                    self._log(f"表 {table_name} 同步被用户取消", "WARNING")
                    break
                if not columns:
                    columns = row.keys()
                batch.append(row)
                if len(batch) >= 1000:
                    self._batch_insert(target_conn, table_name, columns, batch, 1000, "MySQL", pk_columns, conflict)
                    inserted += len(batch)
                    batch = []
                    batch_num += 1
                    # 行级进度（每 1000 行或 10 批上报一次）
                    if total_est and batch_num % 10 == 0:
                        pct = min(99, int(inserted / total_est * 100))
                        if pct > last_progress:
                            last_progress = pct
                            self.progress_callback("row_progress", {
                                "table": table_name, "inserted": inserted, "total_est": total_est, "percent": pct
                            })
            if batch:
                self._batch_insert(target_conn, table_name, columns, batch, 1000, "MySQL", pk_columns, conflict)
                inserted += len(batch)

        self.stats['total_rows'] += inserted
        self._log(f"表 {table_name} 写入完成: {inserted} 行")

        # 重建索引
        if idx_ddl:
            self._log("正在重建索引...")
            self._recreate_indexes(target_conn, table_name, idx_ddl, "MySQL")
            self._log("索引重建完成")

    def _sync_pg_data(self, source_conn, target_conn, table_name, pk_columns, conflict):
        """PostgreSQL 大表数据同步：分批 LIMIT/OFFSET + 多行 VALUES + 冲突检测"""
        # 获取总行数
        total_est = self._get_table_count(source_conn, table_name, "PostgreSQL")
        if total_est and total_est == 0:
            self._log(f"表 {table_name} 无数据，跳过")
            return

        # 获取列信息
        schema = self.source_data.get('schema', 'public')
        cols_info = source_conn.run(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table_name}' AND table_schema = '{schema}'
            ORDER BY ordinal_position
        """)
        columns = [c[0] for c in cols_info]
        if not columns:
            self._log(f"表 {table_name} 无列信息，跳过", "WARNING")
            return

        # 索引优化：暂存并删除非主键索引
        idx_ddl = []
        if conflict != "update":
            idx_ddl = self._get_non_pk_indexes(target_conn, table_name, "PostgreSQL")
            if idx_ddl:
                self._log(f"暂存 {len(idx_ddl)} 个非主键索引，数据同步后重建")
                self._drop_indexes(target_conn, table_name, idx_ddl, "PostgreSQL")

        insert_sql = self._build_insert_sql(table_name, columns, "PostgreSQL", pk_columns, conflict)
        batch_size = 500  # PG 多行 VALUES 用 500 一批
        offset = 0
        inserted = 0
        last_progress = 0

        while not self.cancel_event.is_set():
            # 分批拉取
            rows = source_conn.run(f'SELECT * FROM "{table_name}" ORDER BY 1 OFFSET {offset} LIMIT {batch_size}')
            if not rows or len(rows) == 0:
                break

            # 多行批量写入（一次 sql 包含多个 VALUES）
            batch = []
            for row in rows:
                if self.cancel_event.is_set():
                    break
                # row 是 tuple，转 dict
                row_dict = dict(zip(columns, row))
                batch.append(row_dict)
                if len(batch) >= 200:  # 每 200 行构建一条多行 VALUES
                    self._batch_insert(target_conn, table_name, columns, batch, 200, "PostgreSQL", pk_columns, conflict, insert_sql)
                    inserted += len(batch)
                    batch = []
                    if total_est:
                        pct = min(99, int(inserted / total_est * 100))
                        if pct > last_progress:
                            last_progress = pct
                            self.progress_callback("row_progress", {
                                "table": table_name, "inserted": inserted, "total_est": total_est, "percent": pct
                            })
            if batch:
                self._batch_insert(target_conn, table_name, columns, batch, 200, "PostgreSQL", pk_columns, conflict, insert_sql)
                inserted += len(batch)

            offset += batch_size
            # 如果拉取的数据少于 batch_size，说明已拉完
            if len(rows) < batch_size:
                break

        self.stats['total_rows'] += inserted
        self._log(f"表 {table_name} 写入完成: {inserted} 行")

        # 重建索引
        if idx_ddl:
            self._log("正在重建索引...")
            self._recreate_indexes(target_conn, table_name, idx_ddl, "PostgreSQL")
            self._log("索引重建完成")

    def _batch_insert(self, conn, table_name, columns, rows, batch_size=1000,
                      db_type=None, pk_columns=None, conflict_strategy=None, insert_sql=None):
        """批量写入（MySQL: executemany | PG: 多行 VALUES）"""
        if db_type is None:
            db_type = self.target_data.get('db_type', 'MySQL')

        if db_type == "MySQL":
            sql = insert_sql
            if sql is None:
                sql = self._build_insert_sql(table_name, columns, "MySQL", pk_columns or [], conflict_strategy or "overwrite")
            with conn.cursor() as cursor:
                data = []
                for row in rows:
                    if self.cancel_event.is_set(): break
                    data.append(tuple(row[c] for c in columns))
                    if len(data) >= batch_size:
                        try:
                            cursor.executemany(sql, data)
                        except Exception as e:
                            self._log(f"MySQL 批量写入失败 ({len(data)} 行): {str(e)[:200]}", "ERROR")
                            # 降级：逐行写入
                            for single_row in data:
                                try:
                                    cursor.execute(sql, single_row)
                                except Exception as e2:
                                    self._log(f"行写入失败: {str(e2)[:100]}", "WARNING")
                        data = []
                if data:
                    try:
                        cursor.executemany(sql, data)
                    except Exception as e:
                        self._log(f"MySQL 批量写入失败 ({len(data)} 行): {str(e)[:200]}", "ERROR")
                        for single_row in data:
                            try:
                                cursor.execute(sql, single_row)
                            except Exception as e2:
                                self._log(f"行写入失败: {str(e2)[:100]}", "WARNING")
            conn.commit()
        else:
            # PostgreSQL — 多行 VALUES 构造
            sql = insert_sql
            if sql is None:
                sql = self._build_insert_sql(table_name, columns, "PostgreSQL", pk_columns or [], conflict_strategy or "overwrite")

            # 多行 VALUES: INSERT INTO ... VALUES (:0_0,:0_1,...),(:1_0,:1_1,...),...
            row_placeholders = []
            params = {}
            for i, row in enumerate(rows[:batch_size]):
                if self.cancel_event.is_set(): break
                row_parts = []
                for j, col in enumerate(columns):
                    key = f"r{i}_{j}"
                    row_parts.append(f":{key}")
                    params[key] = row[col] if isinstance(row, dict) else row[j]
                row_placeholders.append("(" + ", ".join(row_parts) + ")")
            if row_placeholders:
                multi_sql = sql.split("VALUES")[0] + "VALUES " + ", ".join(row_placeholders)
                try:
                    conn.run(multi_sql, **params)
                except Exception as e:
                    self._log(f"PG 批量写入失败 ({len(rows)} 行): {str(e)[:200]}", "ERROR")
                    # 降级：逐行写入
                    for row in rows[:batch_size]:
                        if self.cancel_event.is_set(): break
                        row_params = {}
                        for j, col in enumerate(columns):
                            row_params[f":{j}"] = row[col] if isinstance(row, dict) else row[j]
                        try:
                            conn.run(sql, **row_params)
                        except Exception as e2:
                            self._log(f"行写入失败: {str(e2)[:100]}", "WARNING")
