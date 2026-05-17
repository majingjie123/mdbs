"""数据库备份恢复核心模块（纯 Python 模式 + CLI 回退）"""

import os
import re
import subprocess
import threading
import shutil
import pymysql
import pymysql.cursors
from datetime import datetime

from core.ssh_manager import SSHTunnelManager


class BackupManager:
    """数据库备份恢复管理器，支持纯 Python 模式和命令行工具模式"""

    def __init__(self):
        self.ssh_manager = SSHTunnelManager()
        self.process = None          # subprocess 句柄（仅 CLI 模式）
        self.cancel_event = None     # threading.Event

    def _get_python_connection(self, conn_data, database=None):
        """使用 pymysql/pg8000 获取数据库连接（含 SSH 隧道）"""
        db_type = conn_data.get('db_type', 'MySQL')
        host = conn_data['host']
        port = int(conn_data['port'])
        db_name = database or conn_data.get('database')

        # SSH 隧道处理
        if conn_data.get('ssh_enabled'):
            tunnel_host, tunnel_port = self.ssh_manager.start_tunnel(conn_data)
            host = tunnel_host
            port = tunnel_port

        if db_type == "MySQL":
            conn = pymysql.connect(
                host=host, port=port,
                user=conn_data['user'], password=conn_data.get('password'),
                database=db_name, connect_timeout=30, charset='utf8mb4'
            )
            return conn
        else:
            import pg8000.native
            conn = pg8000.native.Connection(
                user=conn_data['user'],
                password=conn_data.get('password'),
                host=host, port=port,
                database=db_name, timeout=30
            )
            return conn

    # ── 工具检测（保留，仅用于 CLI 模式） ─────────────────────

    @staticmethod
    def check_tool(name):
        """检查命令行工具是否可用，返回 (found, path)"""
        path = shutil.which(name)
        return (True, path) if path else (False, None)

    @staticmethod
    def get_available_tools(db_type):
        """返回某数据库类型所需的工具列表和状态"""
        if db_type == "MySQL":
            tools = ["mysqldump", "mysql"]
        else:
            tools = ["pg_dump", "psql"]
        result = {}
        for t in tools:
            found, path = BackupManager.check_tool(t)
            result[t] = {"available": found, "path": path}
        return result

    # ── 纯 Python 备份 ───────────────────────────────────────

    def _format_mysql_value(self, val):
        """将 Python 值格式化为 MySQL SQL 字面量"""
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float):
            return repr(val)
        if isinstance(val, bytes):
            return f"x'{val.hex()}'"
        if isinstance(val, datetime):
            return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
        # 字符串类型
        s = str(val).replace('\\', '\\\\').replace("'", "\\'")
        return f"'{s}'"

    def _backup_mysql_python(self, conn_data, output_path,
                             tables=None, include_data=True, include_structure=True,
                             db_name=None, progress_callback=None, cancel_event=None):
        """纯 Python MySQL 备份"""
        log = _LogCollector(progress_callback)

        conn = self._get_python_connection(conn_data, database=db_name)
        cancel = cancel_event or threading.Event()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        try:
            with conn.cursor() as cursor:
                # 获取表列表
                if tables:
                    table_list = tables
                else:
                    cursor.execute("SHOW TABLES")
                    table_list = [row[0] for row in cursor.fetchall()]

                if not table_list:
                    return False, "数据库中没有任何表"

                total = len(table_list)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"-- MDBS Backup\n")
                    f.write(f"-- Database: {db_name}\n")
                    f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("SET NAMES utf8mb4;\n")
                    f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

                    for idx, table in enumerate(table_list, 1):
                        if cancel.is_set():
                            os.remove(output_path)
                            return False, "备份已取消"

                        table_name = table
                        progress = int((idx - 1) / total * 100)
                        log.info(f"正在处理表 [{idx}/{total}]: {table_name}", progress=progress)

                        # 结构
                        if include_structure:
                            cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                            row = cursor.fetchone()
                            if row:
                                create_sql = row[1]
                                f.write(f"-- Table Structure: `{table_name}`\n")
                                f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                                f.write(create_sql)
                                f.write(";\n\n")
                                log.info(f"  - 结构已导出: {table_name}")

                        # 数据（流式读取，避免大表内存暴涨）
                        if include_data:
                            data_cursor = conn.cursor(pymysql.cursors.SSCursor)
                            data_cursor.execute(f"SELECT * FROM `{table_name}`")
                            columns = [desc[0] for desc in data_cursor.description]
                            col_names = ", ".join(f"`{c}`" for c in columns)
                            row_count = 0
                            batch_size = 500

                            f.write(f"-- Table Data: `{table_name}`\n")

                            while True:
                                if cancel.is_set():
                                    data_cursor.close()
                                    os.remove(output_path)
                                    return False, "备份已取消"

                                batch = data_cursor.fetchmany(batch_size)
                                if not batch:
                                    break

                                for row in batch:
                                    values = ", ".join(self._format_mysql_value(v) for v in row)
                                    f.write(f"INSERT INTO `{table_name}` ({col_names}) VALUES ({values});\n")
                                    row_count += 1

                            data_cursor.close()
                            log.info(f"  - 数据已导出: {table_name} ({row_count} 行)")

                    # 导出自定义函数 / 存储过程 / 触发器
                    if include_structure:
                        # 函数
                        cursor.execute("""
                            SELECT ROUTINE_NAME, ROUTINE_TYPE
                            FROM information_schema.ROUTINES
                            WHERE ROUTINE_SCHEMA = %s
                        """, (db_name,))
                        routines = cursor.fetchall()
                        for rname, rtype in routines:
                            if cancel.is_set():
                                os.remove(output_path)
                                return False, "备份已取消"
                            try:
                                if rtype == "FUNCTION":
                                    cursor.execute(f"SHOW CREATE FUNCTION `{rname}`")
                                else:
                                    cursor.execute(f"SHOW CREATE PROCEDURE `{rname}`")
                                row = cursor.fetchone()
                                if row:
                                    f.write(f"\n-- {rtype}: `{rname}`\n")
                                    f.write(row[2])
                                    f.write(";\n\n")
                                    log.info(f"  - {rtype} 已导出: {rname}")
                            except Exception:
                                pass

                        # 触发器
                        try:
                            cursor.execute("""
                                SELECT TRIGGER_NAME FROM information_schema.TRIGGERS
                                WHERE TRIGGER_SCHEMA = %s
                            """, (db_name,))
                            triggers = cursor.fetchall()
                            for (tname,) in triggers:
                                if cancel.is_set():
                                    os.remove(output_path)
                                    return False, "备份已取消"
                                try:
                                    cursor.execute(f"SHOW CREATE TRIGGER `{tname}`")
                                    row = cursor.fetchone()
                                    if row:
                                        f.write(f"\n-- Trigger: `{tname}`\n")
                                        f.write(row[2])
                                        f.write(";\n\n")
                                        log.info(f"  - 触发器已导出: {tname}")
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

                size = os.path.getsize(output_path)
                log.info(f"备份完成，共 {total} 张表，文件大小: {_fmt_size(size)}", progress=100)
                return True, f"备份成功: {output_path} ({_fmt_size(size)})"

        except Exception as e:
            return False, f"备份失败: {e}"
        finally:
            conn.close()

    def _backup_pg_python(self, conn_data, output_path,
                          tables=None, include_data=True, include_structure=True,
                          db_name=None, progress_callback=None, cancel_event=None):
        """纯 Python PostgreSQL 备份"""
        import pg8000.native

        log = _LogCollector(progress_callback)

        conn = self._get_python_connection(conn_data, database=db_name)
        cancel = cancel_event or threading.Event()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        def escape_pg(val):
            if val is None:
                return "NULL"
            if isinstance(val, bool):
                return "TRUE" if val else "FALSE"
            if isinstance(val, int):
                return str(val)
            if isinstance(val, float):
                return repr(val)
            if isinstance(val, bytes):
                return f"E'\\\\x{val.hex()}'::bytea"
            if isinstance(val, datetime):
                return f"'{val.isoformat()}'"
            s = str(val).replace("'", "''")
            return f"'{s}'"

        try:
            # 获取表列表
            if tables:
                table_list = tables
            else:
                result = conn.run("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                table_list = [row[0] for row in result]

            if not table_list:
                return False, "数据库中没有任何表"

            total = len(table_list)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"-- MDBS Backup\n")
                f.write(f"-- Database: {db_name}\n")
                f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for idx, table in enumerate(table_list, 1):
                    if cancel.is_set():
                        os.remove(output_path)
                        return False, "备份已取消"

                    table_name = table
                    progress = int((idx - 1) / total * 100)
                    log.info(f"正在处理表 [{idx}/{total}]: {table_name}", progress=progress)

                    # 结构
                    if include_structure:
                        # 获取列信息
                        columns_info = conn.run(f"""
                            SELECT
                                column_name, data_type, udt_name,
                                character_maximum_length,
                                is_nullable, column_default,
                                (SELECT pg_catalog.pg_get_serial_sequence(
                                    '{table_name}', column_name
                                ) IS NOT NULL) as is_serial
                            FROM information_schema.columns
                            WHERE table_name = '{table_name}'
                              AND table_schema = 'public'
                            ORDER BY ordinal_position
                        """)

                        pk_cols = conn.run(f"""
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                            WHERE tc.table_name = '{table_name}'
                              AND tc.table_schema = 'public'
                              AND tc.constraint_type = 'PRIMARY KEY'
                            ORDER BY kcu.ordinal_position
                        """)
                        pk_set = {row[0] for row in pk_cols}

                        # 构建 CREATE TABLE
                        cols_def = []
                        for col in columns_info:
                            col_name, data_type, udt_name, char_max, is_nullable, col_default, is_serial = col

                            if char_max and data_type in ('character varying', 'character', 'varchar', 'char'):
                                pg_type = f"{data_type}({char_max})"
                            else:
                                pg_type = udt_name

                            parts = [f'    "{col_name}" {pg_type}']

                            # 处理默认值
                            if is_serial:
                                parts[-1] = f'    "{col_name}" SERIAL'
                            elif col_default:
                                if col_default.startswith("nextval"):
                                    parts[-1] = f'    "{col_name}" SERIAL'
                                elif col_default == "true":
                                    parts.append("DEFAULT TRUE")
                                elif col_default == "false":
                                    parts.append("DEFAULT FALSE")
                                elif col_default.startswith(("'", "0", "1", "(")):
                                    parts.append(f"DEFAULT {col_default}")
                                else:
                                    parts.append(f"DEFAULT {col_default}")

                            if is_nullable == "NO" and not is_serial:
                                parts.append("NOT NULL")

                            cols_def.append(" ".join(parts))

                        # 主键
                        if pk_cols:
                            pk_names = ", ".join(f'"{p[0]}"' for p in pk_cols)
                            cols_def.append(f"    PRIMARY KEY ({pk_names})")

                        f.write(f"-- Table Structure: {table_name}\n")
                        f.write(f"DROP TABLE IF EXISTS {table_name} CASCADE;\n")
                        f.write("CREATE TABLE {0} (\n{1}\n);\n\n".format(
                            table_name, ",\n".join(cols_def)
                        ))
                        log.info(f"  - 结构已导出: {table_name}")

                        # 索引
                        try:
                            index_info = conn.run(f"""
                                SELECT indexdef
                                FROM pg_indexes
                                WHERE tablename = '{table_name}'
                                  AND schemaname = 'public'
                            """)
                            has_index = False
                            for (idef,) in index_info:
                                if cancel.is_set():
                                    os.remove(output_path)
                                    return False, "备份已取消"
                                if "PRIMARY KEY" in idef.upper():
                                    continue
                                if "IF NOT EXISTS" not in idef.upper():
                                    idef = idef.replace(
                                        "CREATE INDEX", "CREATE INDEX IF NOT EXISTS", 1
                                    )
                                    idef = idef.replace(
                                        "CREATE UNIQUE INDEX",
                                        "CREATE UNIQUE INDEX IF NOT EXISTS", 1
                                    )
                                f.write(f"{idef};\n")
                                has_index = True
                            if has_index:
                                f.write("\n")
                        except Exception:
                            pass

                        # 外键
                        try:
                            fk_info = conn.run(f"""
                                SELECT
                                    tc.constraint_name,
                                    kcu.column_name,
                                    ccu.table_name AS ftable,
                                    ccu.column_name AS fcol
                                FROM information_schema.table_constraints tc
                                JOIN information_schema.key_column_usage kcu
                                    ON tc.constraint_name = kcu.constraint_name
                                JOIN information_schema.constraint_column_usage ccu
                                    ON tc.constraint_name = ccu.constraint_name
                                WHERE tc.table_name = '{table_name}'
                                  AND tc.table_schema = 'public'
                                  AND tc.constraint_type = 'FOREIGN KEY'
                                ORDER BY tc.constraint_name, kcu.ordinal_position
                            """)
                            if fk_info:
                                fk_groups = {}
                                for cname, col, ftable, fcol in fk_info:
                                    fk_groups.setdefault(cname, []).append((col, ftable, fcol))
                                for cname, fk_parts in fk_groups.items():
                                    if cancel.is_set():
                                        os.remove(output_path)
                                        return False, "备份已取消"
                                    lcols = ", ".join(f'"{c}"' for c, _, _ in fk_parts)
                                    rcols = ", ".join(f'"{c}"' for _, _, c in fk_parts)
                                    ref_table = fk_parts[0][1]
                                    f.write(
                                        f"ALTER TABLE {table_name} ADD CONSTRAINT {cname} "
                                        f"FOREIGN KEY ({lcols}) REFERENCES {ref_table} ({rcols});\n"
                                    )
                                f.write("\n")
                        except Exception:
                            pass

                    # 数据（流式读取，避免大表内存暴涨）
                    if include_data:
                        batch_size = 500
                        offset = 0
                        col_names = None
                        row_count = 0

                        f.write(f"-- Table Data: {table_name}\n")

                        while True:
                            if cancel.is_set():
                                os.remove(output_path)
                                return False, "备份已取消"

                            rows = conn.run(
                                f'SELECT * FROM "{table_name}" LIMIT {batch_size} OFFSET {offset}'
                            )
                            if not rows:
                                break

                            # 仅在第一批中获取列名
                            if col_names is None:
                                try:
                                    columns = [c['name'] for c in conn.columns]
                                except (AttributeError, TypeError):
                                    pass
                                col_names = ", ".join(f'"{c}"' for c in columns)

                            offset += len(rows)

                            for row in rows:
                                values = ", ".join(escape_pg(v) for v in row)
                                f.write(f"INSERT INTO {table_name} ({col_names}) VALUES ({values});\n")
                                row_count += 1

                        log.info(f"  - 数据已导出: {table_name} ({row_count} 行)")

                # 视图
                if include_structure:
                    try:
                        views = conn.run("""
                            SELECT table_name, view_definition
                            FROM information_schema.views
                            WHERE table_schema = 'public'
                            ORDER BY table_name
                        """)
                        for vname, vdef in views:
                            if cancel.is_set():
                                os.remove(output_path)
                                return False, "备份已取消"
                            f.write(f"-- View: {vname}\n")
                            # view_definition 可能包含 trailing semicolon，确保格式干净
                            f.write(f"CREATE OR REPLACE VIEW {vname} AS\n{vdef.strip()};\n\n")
                            log.info(f"  - 视图已导出: {vname}")
                    except Exception:
                        pass

                    # 函数 / 存储过程
                    try:
                        funcs = conn.run("""
                            SELECT p.proname, pg_catalog.pg_get_functiondef(p.oid)
                            FROM pg_catalog.pg_proc p
                            JOIN pg_catalog.pg_namespace n ON p.pronamespace = n.oid
                            WHERE n.nspname = 'public'
                              AND p.prokind IN ('f', 'p')
                            ORDER BY p.proname
                        """)
                        for fname, fdef in funcs:
                            if cancel.is_set():
                                os.remove(output_path)
                                return False, "备份已取消"
                            f.write(f"-- Function/Procedure: {fname}\n")
                            f.write(f"{fdef}\n\n")
                            log.info(f"  - 函数已导出: {fname}")
                    except Exception:
                        pass

                    # 触发器
                    try:
                        triggers = conn.run("""
                            SELECT tgname, pg_catalog.pg_get_triggerdef(t.oid)
                            FROM pg_catalog.pg_trigger t
                            JOIN pg_catalog.pg_class c ON t.tgrelid = c.oid
                            JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
                            WHERE n.nspname = 'public'
                              AND NOT t.tgisinternal
                            ORDER BY tgname
                        """)
                        for tgname, tgdef in triggers:
                            if cancel.is_set():
                                os.remove(output_path)
                                return False, "备份已取消"
                            f.write(f"-- Trigger: {tgname}\n")
                            f.write(f"{tgdef};\n\n")
                            log.info(f"  - 触发器已导出: {tgname}")
                    except Exception:
                        pass

                size = os.path.getsize(output_path)
                log.info(f"备份完成，共 {total} 张表，文件大小: {_fmt_size(size)}", progress=100)
                return True, f"备份成功: {output_path} ({_fmt_size(size)})"

        except Exception as e:
            return False, f"备份失败: {e}"
        finally:
            conn.close()

    # ── 纯 Python 恢复 ───────────────────────────────────────

    @staticmethod
    def _stream_sql_statements(file_path, cancel_event=None):
        """流式读取 SQL 文件，逐句 yield，避免完整文件加载到内存"""
        with open(file_path, "r", encoding="utf-8") as f:
            current = []
            in_string = False
            string_char = None
            in_block_comment = False

            for line in f:
                if cancel_event and cancel_event.is_set():
                    return

                i = 0
                while i < len(line):
                    ch = line[i]
                    next_ch = line[i + 1] if i + 1 < len(line) else ''

                    if in_block_comment:
                        if ch == '*' and next_ch == '/':
                            in_block_comment = False
                            i += 2
                            continue
                        i += 1
                        continue

                    if in_string:
                        current.append(ch)
                        if ch == '\\':
                            i += 1
                            if i < len(line):
                                current.append(line[i])
                        elif ch == string_char:
                            in_string = False
                        i += 1
                        continue

                    # ── 不在字符串 / 块注释内 ──
                    if ch == '-' and next_ch == '-':
                        # 行注释，跳过本行剩余内容
                        break
                    elif ch == '/' and next_ch == '*':
                        in_block_comment = True
                        i += 2
                        continue
                    elif ch in ("'", '"'):
                        in_string = True
                        string_char = ch
                        current.append(ch)
                    elif ch == ';':
                        current.append(ch)
                        stmt = ''.join(current).strip()
                        if stmt:
                            yield stmt
                        current = []
                    else:
                        current.append(ch)
                    i += 1

            # 文件末尾的剩余内容
            remaining = ''.join(current).strip()
            if remaining:
                yield remaining

    def _restore_mysql_python(self, conn_data, input_path,
                              progress_callback=None, cancel_event=None):
        """纯 Python MySQL 恢复（流式解析，不加载完整文件）"""
        log = _LogCollector(progress_callback)
        cancel = cancel_event or threading.Event()

        conn = self._get_python_connection(conn_data)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                cursor.execute("SET UNIQUE_CHECKS = 0")
                cursor.execute("SET SQL_MODE = ''")

                # 先遍历一遍统计总数（用于进度条）
                total = 0
                for _ in BackupManager._stream_sql_statements(input_path, cancel):
                    total += 1
                if cancel.is_set():
                    return False, "恢复已取消"

                log.info(f"开始恢复，共 {total} 条 SQL 语句")

                # 正式执行（再次流式读取）
                idx = 0
                for stmt in BackupManager._stream_sql_statements(input_path, cancel):
                    if cancel.is_set():
                        return False, "恢复已取消"

                    idx += 1
                    clean_stmt = stmt.rstrip(';').strip()
                    if not clean_stmt or clean_stmt.startswith('--'):
                        continue

                    if idx % 10 == 0 or idx == total:
                        progress = int(idx / total * 100) if total > 0 else 100
                        log.info(f"恢复进度: [{idx}/{total}]", progress=progress)

                    try:
                        cursor.execute(clean_stmt)
                        conn.commit()
                    except Exception as e:
                        err_str = str(e).lower()
                        if any(kw in clean_stmt[:20].upper() for kw in ['SET ', 'DROP ', '--']):
                            continue
                        log.info(f"  语句 [{idx}] 执行警告: {e}")
                        if "table" in err_str and "doesn't exist" in err_str:
                            pass

            log.info("恢复完成", progress=100)
            return True, "恢复成功"
        except Exception as e:
            return False, f"恢复失败: {e}"
        finally:
            conn.close()

    def _restore_pg_python(self, conn_data, input_path,
                           progress_callback=None, cancel_event=None):
        """纯 Python PostgreSQL 恢复"""
        import pg8000.native

        log = _LogCollector(progress_callback)
        cancel = cancel_event or threading.Event()

        conn = self._get_python_connection(conn_data)
        try:
            # 先遍历一遍统计总数（用于进度条）
            total = 0
            for _ in BackupManager._stream_sql_statements(input_path, cancel):
                total += 1
            if cancel.is_set():
                return False, "恢复已取消"

            log.info(f"开始恢复，共 {total} 条 SQL 语句")

            # 正式执行（再次流式读取）
            idx = 0
            for stmt in BackupManager._stream_sql_statements(input_path, cancel):
                if cancel.is_set():
                    return False, "恢复已取消"

                idx += 1
                clean = stmt.rstrip(';').strip()
                if not clean or clean.startswith('--'):
                    continue

                if idx % 10 == 0 or idx == total:
                    progress = int(idx / total * 100) if total > 0 else 100
                    log.info(f"恢复进度: [{idx}/{total}]", progress=progress)

                try:
                    conn.run(clean)
                except Exception as e:
                    err_str = str(e).lower()
                    if any(kw in clean[:20].upper() for kw in ['SET ', 'DROP ']):
                        continue
                    log.info(f"  语句 [{idx}] 执行警告: {e}")
                    if "does not exist" in err_str:
                        pass

            log.info("恢复完成", progress=100)
            return True, "恢复成功"
        except Exception as e:
            return False, f"恢复失败: {e}"
        finally:
            conn.close()

    # ── 统一备份入口 ─────────────────────────────────────────

    def backup_database(self, conn_data, output_path,
                        tables=None, include_data=True, include_structure=True,
                        progress_callback=None, cancel_event=None):
        """
        备份数据库，使用纯 Python 模式（无需外部 CLI 工具）。
        如果 Python 模式不可用，降级为 CLI 工具模式（如已安装）。
        """
        db_type = conn_data.get('db_type', 'MySQL')
        db_name = conn_data.get('database', '')
        if not db_name:
            return False, "未指定数据库名"

        self.cancel_event = cancel_event or threading.Event()

        # 尝试纯 Python 模式
        try:
            if db_type == "MySQL":
                return self._backup_mysql_python(
                    conn_data, output_path, tables,
                    include_data, include_structure,
                    db_name, progress_callback, self.cancel_event
                )
            else:
                return self._backup_pg_python(
                    conn_data, output_path, tables,
                    include_data, include_structure,
                    db_name, progress_callback, self.cancel_event
                )
        except ImportError as e:
            # Python 模式不可用（如未安装 pymysql/pg8000），降级到 CLI
            log = _LogCollector(progress_callback)
            log.info(f"Python 备份引擎不可用 ({e})，尝试使用 CLI 工具...")
            return self._backup_cli(
                conn_data, output_path, tables,
                include_data, include_structure,
                progress_callback, self.cancel_event
            )

    def restore_database(self, conn_data, input_path,
                         progress_callback=None, cancel_event=None):
        """
        恢复数据库，使用纯 Python 模式（无需外部 CLI 工具）。
        如果 Python 模式不可用，降级为 CLI 工具模式（如已安装）。
        """
        if not os.path.isfile(input_path):
            return False, f"备份文件不存在: {input_path}"

        db_type = conn_data.get('db_type', 'MySQL')
        db_name = conn_data.get('database', '')
        if not db_name:
            return False, "未指定目标数据库名"

        self.cancel_event = cancel_event or threading.Event()

        # 尝试纯 Python 模式
        try:
            if db_type == "MySQL":
                return self._restore_mysql_python(
                    conn_data, input_path,
                    progress_callback, self.cancel_event
                )
            else:
                return self._restore_pg_python(
                    conn_data, input_path,
                    progress_callback, self.cancel_event
                )
        except ImportError as e:
            # Python 模式不可用，降级到 CLI
            log = _LogCollector(progress_callback)
            log.info(f"Python 恢复引擎不可用 ({e})，尝试使用 CLI 工具...")
            return self._restore_cli(
                conn_data, input_path,
                progress_callback, self.cancel_event
            )

    # ── CLI 模式（保留作降级回退） ───────────────────────────

    def _build_conn_flags(self, conn_data, use_tunnel=False):
        """
        构建命令行连接参数列表（不含可执行文件名）。
        如果 use_tunnel=True 且启用了 SSH，返回隧道本地端点。
        返回 (flags_list, env_dict, actual_host, actual_port)
        """
        db_type = conn_data.get('db_type', 'MySQL')
        host = conn_data['host']
        port = str(conn_data.get('port', '3306' if db_type == 'MySQL' else '5432'))
        user = conn_data.get('user', '')
        password = conn_data.get('password', '')

        # SSH 隧道处理
        if use_tunnel and conn_data.get('ssh_enabled'):
            try:
                local_host, local_port = self.ssh_manager.start_tunnel(conn_data)
                host = local_host
                port = str(local_port)
            except Exception as e:
                raise Exception(f"SSH 隧道启动失败: {e}")

        flags = []
        env = os.environ.copy()

        if db_type == "MySQL":
            flags.extend(["-h", host, "-P", port, "-u", user])
            if password:
                flags.append(f"--password={password}")
        else:
            flags.extend(["-h", host, "-p", port, "-U", user])
            if password:
                env["PGPASSWORD"] = password

        return flags, env, host, port

    def _backup_cli(self, conn_data, output_path,
                    tables=None, include_data=True, include_structure=True,
                    progress_callback=None, cancel_event=None):
        """使用 mysqldump/pg_dump 进行备份（降级回退）"""
        db_type = conn_data.get('db_type', 'MySQL')
        db_name = conn_data.get('database', '')

        tool_name = "mysqldump" if db_type == "MySQL" else "pg_dump"
        found, tool_path = self.check_tool(tool_name)
        if not found:
            return False, f"未找到 {tool_name}，Python 引擎不可用时请安装该工具"

        log = _LogCollector(progress_callback)
        log.info(f"开始备份 {db_type} 数据库: {db_name} -> {output_path}")

        try:
            flags, env, host, port = self._build_conn_flags(conn_data, use_tunnel=True)
        except Exception as e:
            return False, f"连接参数构建失败: {e}"

        cmd = [tool_path] + flags

        if db_type == "MySQL":
            if not include_data:
                cmd.append("--no-data")
            if not include_structure:
                cmd.append("--no-create-info")
            cmd.extend(["--routines", "--triggers", "--events", "--skip-comments"])
            cmd.append(db_name)
            if tables:
                cmd.extend(tables)
        else:
            cmd.append(f"--dbname={db_name}")
            if not include_structure and include_data:
                cmd.append("--data-only")
            elif include_structure and not include_data:
                cmd.append("--schema-only")
            if not include_data and not include_structure:
                return False, "至少需要选择备份结构或数据"
            if tables:
                cmd.extend([f"--table={t}" for t in tables])

        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                self.process = subprocess.Popen(
                    cmd, stdout=f, stderr=subprocess.PIPE, env=env, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                while self.process.poll() is None:
                    if cancel_event and cancel_event.is_set():
                        self.process.kill()
                        self.process.wait()
                        try:
                            os.remove(output_path)
                        except OSError:
                            pass
                        return False, "备份已取消"
                    self.cancel_event.wait(0.3)

                stderr_output = self.process.stderr.read()
                self.process.stderr.close()

            if self.process.returncode == 0:
                size = os.path.getsize(output_path)
                log.info(f"备份完成，文件大小: {_fmt_size(size)}")
                return True, f"备份成功: {output_path} ({_fmt_size(size)})"
            else:
                try:
                    if os.path.getsize(output_path) == 0:
                        os.remove(output_path)
                except OSError:
                    pass
                error_msg = stderr_output.strip() or f"退出码: {self.process.returncode}"
                return False, f"备份失败: {error_msg}"

        except FileNotFoundError:
            return False, f"找不到可执行文件: {tool_path}"
        except Exception as e:
            return False, f"备份过程异常: {e}"
        finally:
            self.process = None

    def _restore_cli(self, conn_data, input_path,
                     progress_callback=None, cancel_event=None):
        """使用 mysql/psql 进行恢复（降级回退）"""
        if not os.path.isfile(input_path):
            return False, f"备份文件不存在: {input_path}"

        db_type = conn_data.get('db_type', 'MySQL')
        db_name = conn_data.get('database', '')

        tool_name = "mysql" if db_type == "MySQL" else "psql"
        found, tool_path = self.check_tool(tool_name)
        if not found:
            return False, f"未找到 {tool_name}，Python 引擎不可用时请安装该工具"

        log = _LogCollector(progress_callback)
        log.info(f"开始恢复 {db_type} 数据库: {input_path} -> {db_name}")

        try:
            flags, env, host, port = self._build_conn_flags(conn_data, use_tunnel=True)
        except Exception as e:
            return False, f"连接参数构建失败: {e}"

        cmd = [tool_path] + flags

        if db_type == "MySQL":
            cmd.append(db_name)
            redirect_input = open(input_path, "r", encoding="utf-8")
            redirect_source = redirect_input
        else:
            cmd.extend(["-d", db_name, "-f", input_path])
            redirect_input = None
            redirect_source = None

        try:
            self.process = subprocess.Popen(
                cmd, stdin=redirect_input,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            while self.process.poll() is None:
                if cancel_event and cancel_event.is_set():
                    self.process.kill()
                    self.process.wait()
                    return False, "恢复已取消"
                self.cancel_event.wait(0.3)

            stdout_output = self.process.stdout.read() if self.process.stdout else ""
            stderr_output = self.process.stderr.read() if self.process.stderr else ""
            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()
            if redirect_input:
                redirect_input.close()

            if self.process.returncode == 0:
                log.info("恢复完成")
                return True, "恢复成功"
            else:
                err_lines = [l for l in stderr_output.strip().split("\n")
                             if l.strip() and "NOTICE:" not in l]
                error_msg = "\n".join(err_lines[:10]) or f"退出码: {self.process.returncode}"
                return False, f"恢复失败: {error_msg}"

        except FileNotFoundError:
            return False, f"找不到可执行文件: {tool_path}"
        except Exception as e:
            return False, f"恢复过程异常: {e}"
        finally:
            self.process = None


class _LogCollector:
    """简易日志收集器，包装回调函数"""
    def __init__(self, callback=None):
        self.callback = callback
        self.messages = []

    def info(self, msg, **kwargs):
        self.messages.append(msg)
        if self.callback:
            self.callback(msg, **kwargs)


def _fmt_size(size_bytes):
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"