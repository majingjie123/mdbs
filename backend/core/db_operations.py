import pymysql
import re
import os
from core.ssh_manager import SSHTunnelManager

class DBOperations:
    def __init__(self):
        self.ssh_manager = SSHTunnelManager()

    def get_connection(self, conn_data, database=None):
        """获取数据库连接，支持 MySQL 和 PostgreSQL"""
        db_type = conn_data.get('db_type', 'MySQL')
        host = conn_data['host']
        port = int(conn_data['port'])
        db_name = database or conn_data.get('database')
        
        if conn_data.get('ssh_enabled'):
            tunnel_host, tunnel_port = self.ssh_manager.start_tunnel(conn_data)
            host = tunnel_host
            port = tunnel_port

        try:
            if db_type == "MySQL":
                return pymysql.connect(
                    host=host, port=port,
                    user=conn_data['user'], password=conn_data.get('password'),
                    database=db_name, connect_timeout=30, charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
            else:
                import pg8000.native
                # pg8000.native 默认返回的是字典列表，且连接更现代
                conn = pg8000.native.Connection(
                    user=conn_data['user'],
                    password=conn_data.get('password'),
                    host=host,
                    port=port,
                    database=db_name,
                    timeout=10
                )
                return conn
        except Exception as e:
            raise Exception(f"数据库连接失败 ({db_type}): {str(e)}")

    def disconnect(self, conn_data_or_id):
        """断开连接，释放隧道资源。接受 conn_id int 或 conn_data dict。"""
        conn_id = None
        conn_data = None
        if isinstance(conn_data_or_id, int):
            conn_id = conn_data_or_id
        else:
            conn_data = conn_data_or_id
            conn_id = conn_data.get('id')

        if conn_id is not None:
            try:
                self.ssh_manager.stop_tunnel(conn_id)
            except Exception:
                pass

    def test_connection(self, conn_data):
        """测试数据库连接 (增强版：支持错误清洗与智能检测)"""
        db_type = conn_data.get('db_type', 'MySQL')
        try:
            conn = self.get_connection(conn_data)
            if hasattr(conn, 'close'):
                conn.close()
            return True, "数据库连接成功"
        except Exception as e:
            err_msg = str(e)
            
            # --- PostgreSQL 专用优化 ---
            if db_type == "PostgreSQL":
                # 尝试从字典格式的错误中提取核心消息
                if isinstance(e.args[0], dict) and 'M' in e.args[0]:
                    err_msg = e.args[0]['M']
                elif "database" in err_msg and "does not exist" in err_msg:
                    # 智能检测：如果目标库不存在，验证账号密码是否正确
                    try:
                        # 尝试连接默认的 postgres 库
                        temp_conn = self.get_connection(conn_data, database="postgres")
                        if hasattr(temp_conn, 'close'): temp_conn.close()
                        return False, f"账号密码正确，但目标数据库 [{conn_data.get('database')}] 不存在。"
                    except:
                        pass # 默认库也连不上，按原错误返回
            
            return False, err_msg

    def get_databases(self, conn_data):
        """获取服务器上所有的数据库列表"""
        db_type = conn_data.get('db_type', 'MySQL')
        # 连接时不指定数据库（PostgreSQL 默认连 postgres）
        target_db = None if db_type == "MySQL" else "postgres"
        
        conn = self.get_connection(conn_data, database=target_db)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute("SHOW DATABASES")
                    system_dbs = ['information_schema', 'mysql', 'performance_schema', 'sys']
                    return [row['Database'] for row in cursor.fetchall() if row['Database'] not in system_dbs]
            else:
                # PostgreSQL
                res = conn.run("SELECT datname FROM pg_database WHERE datistemplate = false")
                # 仅过滤掉真正无关的系统库，保留 postgres（用户可能在里面存表）
                system_dbs = ['information_schema']
                return [row[0] for row in res if row[0] not in system_dbs]
        finally:
            if hasattr(conn, 'close'): conn.close()

    def create_database(self, conn_data, db_params):
        """创建一个新的数据库，支持详细参数"""
        db_type = conn_data.get('db_type', 'MySQL')
        target_db = None if db_type == "MySQL" else "postgres"
        db_name = db_params['name']
        
        conn = self.get_connection(conn_data, database=target_db)
        try:
            if db_type == "MySQL":
                charset = db_params.get('charset', 'utf8mb4')
                collation = db_params.get('collation', 'utf8mb4_general_ci')
                sql = f"CREATE DATABASE `{db_name}` DEFAULT CHARACTER SET {charset} COLLATE {collation}"
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    conn.commit()
            else:
                # PostgreSQL
                encoding = db_params.get('encoding', 'UTF8')
                owner = db_params.get('owner')
                owner_stmt = f' OWNER = "{owner}"' if owner else ""
                sql = f'CREATE DATABASE "{db_name}" ENCODING = \'{encoding}\'{owner_stmt}'
                conn.run(sql)
            return True, "数据库创建成功"
        except Exception as e:
            return False, str(e)
        finally:
            if hasattr(conn, 'close'): conn.close()

    def delete_database(self, conn_data, db_name):
        """删除指定的数据库"""
        db_type = conn_data.get('db_type', 'MySQL')
        target_db = None if db_type == "MySQL" else "postgres"
        
        conn = self.get_connection(conn_data, database=target_db)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE `{db_name}`")
                    conn.commit()
            else:
                # PostgreSQL 需要处理活动连接问题（简单处理：强制断开或要求无活动连接）
                # 暂时执行标准 DROP
                conn.run(f'DROP DATABASE "{db_name}"')
            return True, "数据库删除成功"
        except Exception as e:
            return False, str(e)
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_schemas(self, conn_data, database=None):
        """获取指定数据库的所有 Schema (仅限 PostgreSQL)"""
        db_type = conn_data.get('db_type', 'MySQL')
        if db_type == "MySQL": return []
        
        conn = self.get_connection(conn_data, database=database)
        try:
            sql = "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' ORDER BY 1"
            return [row[0] for row in conn.run(sql)]
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_tables(self, conn_data, database=None, schema=None):
        """拉取表名列表 (支持指定 Schema)，返回包含备注的详细信息"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
                    key = f'Tables_in_{database or conn_data.get("database")}'
                    tables = []
                    for row in cursor.fetchall():
                        table_name = row[key]
                        table_comment = row.get('Comment', '') or ''
                        tables.append({'name': table_name, 'comment': table_comment})
                    return tables
            else:
                # PostgreSQL
                target_schema = schema or 'public'
                sql = """
                    SELECT c.relname, COALESCE(obj_description(c.oid, 'pg_class'), '')
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'r' AND n.nspname = :schema
                    ORDER BY 1
                """
                tables = []
                for row in conn.run(sql, schema=target_schema):
                    tables.append({'name': row[0], 'comment': row[1] or ''})
                return tables
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_views(self, conn_data, database=None, schema=None):
        """获取视图列表 (支持指定 Schema)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
                    key = f'Tables_in_{database or conn_data.get("database")}'
                    return [row[key] for row in cursor.fetchall()]
            else:
                target_schema = schema or 'public'
                sql = "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'v' AND n.nspname = :schema ORDER BY 1"
                return [row[0] for row in conn.run(sql, schema=target_schema)]
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_functions(self, conn_data, database=None, schema=None):
        """获取函数/过程列表 (支持指定 Schema)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    sql = "SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = %s"
                    cursor.execute(sql, (database or conn_data.get('database'),))
                    return [{"name": row['ROUTINE_NAME'], "type": row['ROUTINE_TYPE']} for row in cursor.fetchall()]
            else:
                # PostgreSQL
                target_schema = schema or 'public'
                try:
                    ver_res = conn.run("SHOW server_version_num")
                    ver_num = int(ver_res[0][0]) if ver_res else 110000
                except:
                    ver_num = 110000

                type_clause = "CASE WHEN p.prokind = 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END"
                if ver_num < 110000:
                    type_clause = "'FUNCTION'"

                sql = f"""
                    SELECT p.proname, {type_clause} as type
                    FROM pg_proc p 
                    JOIN pg_namespace n ON n.oid = p.pronamespace 
                    WHERE n.nspname = :schema
                    ORDER BY 1
                """
                return [{"name": row[0], "type": row[1]} for row in conn.run(sql, schema=target_schema)]
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_view_ddl(self, conn_data, view_name, database=None):
        """获取视图的 CREATE VIEW 语句"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW CREATE VIEW `{view_name}`")
                    res = cursor.fetchone()
                    return res['Create View'] if res else ""
            else:
                # PostgreSQL
                actual_view = view_name.split('.')[-1]
                schema = view_name.split('.')[0] if '.' in view_name else 'public'
                sql = "SELECT pg_get_viewdef(:view_name, true)"
                res = conn.run(sql, view_name=f"{schema}.{actual_view}")
                if res:
                    return f"CREATE OR REPLACE VIEW {view_name} AS\n{res[0][0]}"
                return ""
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_function_ddl(self, conn_data, func_name, func_type="FUNCTION", database=None):
        """获取函数/过程的定义"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cmd = "SHOW CREATE FUNCTION" if func_type == "FUNCTION" else "SHOW CREATE PROCEDURE"
                    cursor.execute(f"{cmd} `{func_name}`")
                    res = cursor.fetchone()
                    key = 'Create Function' if func_type == "FUNCTION" else 'Create Procedure'
                    return res[key] if res else ""
            else:
                # PostgreSQL
                sql = "SELECT pg_get_functiondef(:func_name::regproc)"
                res = conn.run(sql, func_name=func_name)
                return res[0][0] if res else ""
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_function_metadata(self, conn_data, func_name, database=None):
        """获取函数的详细元数据 (用于编辑窗口)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    # 获取基本信息
                    sql = "SELECT * FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = %s AND ROUTINE_NAME = %s"
                    cursor.execute(sql, (database or conn_data.get('database'), func_name))
                    routine = cursor.fetchone()
                    
                    # 获取参数
                    sql = "SELECT * FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA = %s AND SPECIFIC_NAME = %s ORDER BY ORDINAL_POSITION"
                    cursor.execute(sql, (database or conn_data.get('database'), func_name))
                    params = cursor.fetchall()
                    
                    return {"info": routine, "params": params}
            else:
                # PostgreSQL 适配简化处理，通常编辑时直接拉 DDL 修改
                return {}
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_primary_keys(self, conn_data, table_name, database=None, schema=None):
        """获取表的主键名称列表"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    # 如果 table_name 包含库名 (db.table)，需要拆分
                    actual_table = table_name.split('.')[-1]
                    cursor.execute(f"SHOW KEYS FROM `{actual_table}` WHERE Key_name = 'PRIMARY'")
                    return [row['Column_name'] for row in cursor.fetchall()]
            else:
                # PostgreSQL
                actual_table = table_name.split('.')[-1]
                target_schema = schema or 'public'
                sql = """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    JOIN pg_namespace n ON n.oid = (
                        SELECT relnamespace FROM pg_class WHERE oid = :table_name::regclass
                    )
                    WHERE i.indrelid = :table_name::regclass AND i.indisprimary
                """
                # 使用 schema.table 格式以避免歧义
                qualified_name = f"{target_schema}.{actual_table}"
                return [row[0] for row in conn.run(sql, table_name=qualified_name)]
        except:
            return []
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_table_structure(self, conn_data, database=None, schema=None):
        """获取指定数据库/模式所有表的结构"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            all_structures = {}
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    # MySQL 暂不处理 schema (映射为 database)
                    cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
                    tables = [row[f'Tables_in_{database or conn_data.get("database")}'] for row in cursor.fetchall()]
                    for table in tables:
                        try:
                            cursor.execute(f"SHOW TABLE STATUS LIKE '{table}'")
                            table_info = cursor.fetchone()
                            table_comment = table_info.get('Comment', '') if table_info else ''
                            
                            cursor.execute(f"SHOW FULL COLUMNS FROM `{table}`")
                            columns = cursor.fetchall()
                            all_structures[table] = {
                                'comment': table_comment,
                                'columns': columns
                            }
                        except Exception as table_err:
                            print(f"警告: 无法获取 MySQL 表 {table} 的结构: {table_err}")
                            continue
            else:
                # PostgreSQL
                # 如果提供了 schema，则精确过滤；否则拉取所有用户模式
                where_clause = "n.nspname = :schema" if schema else "n.nspname NOT LIKE 'pg_%' AND n.nspname != 'information_schema'"
                
                tables_sql = f"""
                    SELECT 
                        n.nspname as schema_name,
                        c.relname as table_name,
                        c.oid as table_oid
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'r' 
                      AND {where_clause}
                    ORDER BY n.nspname, c.relname
                """
                tables_res = conn.run(tables_sql, schema=schema) if schema else conn.run(tables_sql)
                
                for row in tables_res:
                    row_schema = row[0]
                    table = row[1]
                    table_oid = row[2]
                    
                    # 统一显示名称
                    display_name = f"{row_schema}.{table}" if row_schema != 'public' else table
                    
                    try:
                        # 获取表注释
                        comment_res = conn.run("SELECT obj_description(:oid, 'pg_class')", oid=table_oid)
                        table_comment = comment_res[0][0] if comment_res and comment_res[0][0] else ""
                        
                        # 获取列详细信息
                        cols_sql = """
                            SELECT 
                                a.attname as column_name,
                                pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type,
                                a.attnotnull as is_not_null,
                                (SELECT substring(pg_get_expr(d.adbin, d.adrelid) for 128)
                                 FROM pg_attrdef d
                                 WHERE d.adrelid = a.attrelid AND d.adnum = a.attnum AND a.atthasdef) as column_default,
                                col_description(a.attrelid, a.attnum) as column_comment
                            FROM pg_attribute a
                            WHERE a.attrelid = :oid 
                              AND a.attnum > 0 
                              AND NOT a.attisdropped
                            ORDER BY a.attnum
                        """
                        cols_res = conn.run(cols_sql, oid=table_oid)
                        
                        columns = []
                        for c in cols_res:
                            columns.append({
                                'Field': c[0],
                                'Type': c[1],
                                'Collation': '',
                                'Null': 'NO' if c[2] else 'YES',
                                'Key': '', 
                                'Default': str(c[3]) if c[3] is not None else '',
                                'Extra': '',
                                'Comment': c[4] if c[4] else ''
                            })
                        
                        all_structures[display_name] = {
                            'comment': table_comment,
                            'columns': columns
                        }
                    except Exception as table_err:
                        print(f"警告: 无法获取表 {display_name} (OID: {table_oid}) 的结构: {table_err}")
                        continue
            return all_structures
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_relations(self, conn_data, database=None):
        """获取数据库中的外键关联关系 (优化版)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            relations = []
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    sql = """
                        SELECT 
                            TABLE_NAME, COLUMN_NAME, 
                            REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME 
                        FROM information_schema.KEY_COLUMN_USAGE 
                        WHERE TABLE_SCHEMA = %s 
                        AND REFERENCED_TABLE_NAME IS NOT NULL
                    """
                    cursor.execute(sql, (database or conn_data.get('database'),))
                    for row in cursor.fetchall():
                        relations.append({
                            'table': row['TABLE_NAME'],
                            'column': row['COLUMN_NAME'],
                            'ref_table': row['REFERENCED_TABLE_NAME'],
                            'ref_column': row['REFERENCED_COLUMN_NAME']
                        })
            else:
                # PostgreSQL: 使用底层 pg_constraint 查询，彻底解决关联拉取不到的问题
                sql = """
                    SELECT
                        conname AS constraint_name,
                        (SELECT nspname FROM pg_namespace WHERE oid=con.connamespace) AS schema_name,
                        (SELECT relname FROM pg_class WHERE oid=con.conrelid) AS table_name,
                        (SELECT attname FROM pg_attribute WHERE attrelid=con.conrelid AND attnum=con.conkey[1]) AS column_name,
                        (SELECT relname FROM pg_class WHERE oid=con.confrelid) AS foreign_table_name,
                        (SELECT attname FROM pg_attribute WHERE attrelid=con.confrelid AND attnum=con.confkey[1]) AS foreign_column_name
                    FROM pg_constraint con
                    WHERE contype = 'f'
                    ORDER BY conname
                """
                res = conn.run(sql)
                for row in res:
                    schema = row[1]
                    # 仅处理非系统模式的关联
                    if schema not in ('information_schema', 'pg_catalog') and not schema.startswith('pg_'):
                        relations.append({
                            'table': f"{schema}.{row[2]}" if schema != 'public' else row[2],
                            'column': row[3],
                            'ref_table': row[4], # 这里通常主表也是同模式，简化处理
                            'ref_column': row[5]
                        })
            return relations
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_table_ddl(self, conn_data, table_name, database=None, schema=None):
        """获取表的 CREATE TABLE 语句 (支持指定 Schema)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                    res = cursor.fetchone()
                    return res['Create Table'] if res else ""
            else:
                # PostgreSQL
                target_schema = schema or 'public'
                # 简化版实现：通过系统表拼接
                sql = f"""
                    SELECT 'CREATE TABLE ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname) || ' (' || 
                           array_to_string(array_agg(quote_ident(a.attname) || ' ' || pg_catalog.format_type(a.atttypid, a.atttypmod) || 
                           CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE '' END), ', ') || ');' 
                    FROM pg_class c 
                    JOIN pg_namespace n ON n.oid = c.relnamespace 
                    JOIN pg_attribute a ON a.attrelid = c.oid 
                    WHERE n.nspname = :schema AND c.relname = :table AND a.attnum > 0 AND NOT a.attisdropped 
                    GROUP BY n.nspname, c.relname
                """
                res = conn.run(sql, schema=target_schema, table=table_name)
                return res[0][0] if res else ""
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_table_columns_detailed(self, conn_data, table_name, database=None, schema=None):
        """获取表的详细字段信息 (支持指定 Schema)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
                    return cursor.fetchall()
            else:
                # PostgreSQL
                target_schema = schema or 'public'
                sql = """
                    SELECT 
                        a.attname as Field,
                        pg_catalog.format_type(a.atttypid, a.atttypmod) as Type,
                        '' as Collation,
                        CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END as "Null",
                        CASE WHEN (SELECT 1 FROM pg_index i WHERE i.indrelid = a.attrelid AND a.attnum = ANY(i.indkey) AND i.indisprimary) = 1 THEN 'PRI' ELSE '' END as "Key",
                        pg_get_expr(d.adbin, d.adrelid) as "Default",
                        '' as Extra,
                        col_description(a.attrelid, a.attnum) as Comment
                    FROM pg_attribute a
                    LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = :table AND n.nspname = :schema
                      AND a.attnum > 0 AND NOT a.attisdropped
                    ORDER BY a.attnum
                """
                res = conn.run(sql, table=table_name, schema=target_schema)
                cols = []
                for row in res:
                    cols.append({
                        'Field': row[0], 'Type': row[1], 'Collation': row[2],
                        'Null': row[3], 'Key': row[4], 'Default': row[5],
                        'Extra': row[6], 'Comment': row[7]
                    })
                return cols
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_table_indexes_detailed(self, conn_data, table_name, database=None, schema=None):
        """获取表的详细索引信息 (支持指定 Schema)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW INDEX FROM `{table_name}`")
                    return cursor.fetchall()
            else:
                # PostgreSQL
                target_schema = schema or 'public'
                sql = """
                    SELECT
                        i.relname as index_name,
                        a.attname as column_name,
                        ix.indisunique as is_unique,
                        ix.indisprimary as is_primary,
                        am.amname as index_type
                    FROM pg_class t
                    JOIN pg_index ix ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                    JOIN pg_am am ON i.relam = am.oid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE t.relname = :table AND n.nspname = :schema
                """
                res = conn.run(sql, table=table_name, schema=target_schema)
                idx = []
                for row in res:
                    idx.append({
                        'Key_name': row[0], 'Column_name': row[1],
                        'Non_unique': 0 if row[2] else 1,
                        'Index_type': row[4], 'Is_Primary': row[3]
                    })
                return idx
        finally:
            if hasattr(conn, 'close'): conn.close()

    def get_table_options_detailed(self, conn_data, table_name, database=None, schema=None):
        """获取表选项 (支持指定 Schema)"""
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW TABLE STATUS LIKE '{table_name}'")
                    return cursor.fetchone()
            else:
                # PostgreSQL
                target_schema = schema or 'public'
                sql = """
                    SELECT 
                        obj_description(c.oid, 'pg_class') as comment,
                        pg_catalog.pg_get_userbyid(c.relowner) as owner
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = :table AND n.nspname = :schema
                """
                res = conn.run(sql, table=table_name, schema=target_schema)
                if res:
                    return {'Comment': res[0][0], 'Owner': res[0][1]}
                return {}
        finally:
            if hasattr(conn, 'close'): conn.close()


    def execute_sql_from_file(self, conn_data, file_path, database=None, cancel_event=None, schema=None, progress_callback=None):
        """
        从文件流式读取并执行 SQL，极其节省内存，适合 GB 级大文件。
        """
        if not os.path.exists(file_path):
            raise Exception(f"文件不存在: {file_path}")
            
        file_size = os.path.getsize(file_path)
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        
        try:
            if db_type != "MySQL" and schema:
                conn.run(f'SET search_path TO "{schema}"')
                
            if db_type == "MySQL":
                cursor = conn.cursor()
                cursor.execute("SET autocommit=0")
            else:
                conn.run("BEGIN")
                
            current_statement = []
            in_string = False
            quote_char = None
            in_line_comment = False
            in_block_comment = False
            
            processed_bytes = 0
            stmt_count = 0
            last_progress_pct = -1
            
            # 使用流式读取，每次读 64KB
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    
                    processed_bytes += len(chunk.encode('utf-8'))
                    
                    # 进度反馈 (基于文件字节偏移)
                    if progress_callback:
                        pct = int((processed_bytes / file_size) * 100)
                        if pct != last_progress_pct:
                            progress_callback(pct, f"正在解析并执行... {pct}% (已处理 {processed_bytes//1024//1024} MB)")
                            last_progress_pct = pct

                    # 字符级解析（虽然稍慢，但对于 100MB 级别文件在后台执行是完全可以接受的）
                    i = 0
                    chunk_len = len(chunk)
                    while i < chunk_len:
                        if cancel_event and cancel_event.is_set():
                            raise Exception("执行已被用户中止")
                            
                        char = chunk[i]
                        next_char = chunk[i+1] if i + 1 < chunk_len else None
                        
                        # 逻辑同 split_sql_statements 但增加了即时执行
                        if not in_string and not in_line_comment:
                            if not in_block_comment and char == '/' and next_char == '*':
                                in_block_comment = True
                                current_statement.append(char)
                                current_statement.append(next_char)
                                i += 2
                                continue
                            elif in_block_comment and char == '*' and next_char == '/':
                                in_block_comment = False
                                current_statement.append(char)
                                current_statement.append(next_char)
                                i += 2
                                continue
                        
                        if in_block_comment:
                            current_statement.append(char)
                            i += 1
                            continue
                            
                        if not in_string and not in_block_comment:
                            if not in_line_comment and ((char == '-' and next_char == '-') or char == '#'):
                                in_line_comment = True
                            elif in_line_comment and char == '\n':
                                in_line_comment = False
                        
                        if in_line_comment:
                            current_statement.append(char)
                            i += 1
                            continue
                            
                        if (char == "'" or char == '"' or char == '`') and (i == 0 or chunk[i-1] != '\\'):
                            if not in_string:
                                in_string = True
                                quote_char = char
                            elif char == quote_char:
                                in_string = False
                                quote_char = None
                        
                        if char == ';' and not in_string:
                            stmt = "".join(current_statement).strip()
                            if stmt:
                                # 立即执行
                                if db_type == "MySQL":
                                    cursor.execute(stmt)
                                else:
                                    conn.run(stmt)
                                stmt_count += 1
                            current_statement = []
                        else:
                            current_statement.append(char)
                        i += 1
            
            # 处理末尾
            stmt = "".join(current_statement).strip()
            if stmt:
                if db_type == "MySQL": cursor.execute(stmt)
                else: conn.run(stmt)
                stmt_count += 1
            
            if db_type == "MySQL":
                conn.commit()
                cursor.execute("SET autocommit=1")
                cursor.close()
            else:
                conn.run("COMMIT")
                
            return True, stmt_count
            
        except Exception:
            if db_type == "MySQL": conn.rollback()
            else: conn.run("ROLLBACK")
            raise
        finally:
            if hasattr(conn, 'close'): conn.close()

    def split_sql_statements(self, sql, progress_callback=None):
        """
        智能拆分 SQL 脚本为多条独立语句。
        使用切片替代字符列表，大幅减少内存分配和 join 开销。
        """
        if not sql:
            return []

        statements = []
        in_string = False
        quote_char = None
        in_line_comment = False
        in_block_comment = False

        sql_len = len(sql)
        stmt_start = 0  # 当前语句起始位置（切片用，替代字符列表）
        i = 0
        last_progress_pct = -1

        while i < sql_len:
            # 进度反馈（对于大脚本）
            if progress_callback and i % 100000 == 0:
                pct = int((i / sql_len) * 100)
                if pct != last_progress_pct:
                    progress_callback(pct, f"正在解析 SQL 脚本... {pct}%")
                    last_progress_pct = pct

            char = sql[i]
            next_char = sql[i+1] if i + 1 < sql_len else None

            # 处理块注释 /* ... */  — 跳过注释内容，不拷贝到结果
            if not in_string and not in_line_comment:
                if not in_block_comment and char == '/' and next_char == '*':
                    in_block_comment = True
                    i += 2
                    continue
                elif in_block_comment and char == '*' and next_char == '/':
                    in_block_comment = False
                    i += 2
                    continue

            if in_block_comment:
                i += 1
                continue

            # 处理单行注释 -- 或 #
            if not in_string and not in_block_comment:
                if not in_line_comment and ((char == '-' and next_char == '-') or char == '#'):
                    in_line_comment = True
                elif in_line_comment and char == '\n':
                    in_line_comment = False

            if in_line_comment:
                i += 1
                continue

            # 处理字符串引用
            if (char == "'" or char == '"' or char == '`') and (i == 0 or sql[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None

            # 语句结束符 — 切片代替字符列表
            if char == ';' and not in_string:
                stmt = sql[stmt_start:i].strip()
                if stmt:
                    statements.append(stmt)
                stmt_start = i + 1

            i += 1

        # 最后的残留部分
        stmt = sql[stmt_start:].strip()
        if stmt:
            statements.append(stmt)

        return statements

    def _batch_inserts(self, statements):
        """将连续同表的单行 INSERT ... VALUES (...) 合并为批量多行写入，减少 MySQL 网络往返。"""
        if not statements:
            return statements

        # 匹配 INSERT INTO tablename [(cols)] VALUES 前缀
        pat = re.compile(
            r"^(INSERT\s+INTO\s+(?:`?\w+`?\.)?`?\w+`?\s*(?:\([^)]*\))?\s*VALUES\s*)(.*)$",
            re.IGNORECASE | re.DOTALL
        )

        result = []
        batch_prefix = None
        batch_values = []
        MAX_BATCH = 100  # 单批上限，避免超出 max_allowed_packet

        def _flush():
            nonlocal batch_prefix, batch_values
            if batch_values:
                if len(batch_values) == 1:
                    result.append(batch_prefix.rstrip() + " " + batch_values[0].rstrip(";"))
                else:
                    result.append(batch_prefix.rstrip() + " " + ", ".join(v.rstrip(";") for v in batch_values))
            batch_prefix = None
            batch_values = []

        for stmt in statements:
            s = stmt.strip()
            m = pat.match(s)
            if m:
                prefix, values = m.group(1), m.group(2).strip()
                if batch_prefix is not None and prefix == batch_prefix and len(batch_values) < MAX_BATCH:
                    batch_values.append(values)
                else:
                    _flush()
                    batch_prefix = prefix
                    batch_values = [values]
            else:
                _flush()
                result.append(s)

        _flush()
        return result

    def execute_sql(self, conn_data, sql, database=None, params=None, cancel_event=None, schema=None, progress_callback=None, limit=1000, offset=0):
        """执行任意 SQL 并返回 (columns, rows, affected_count, is_query, truncated, total)"""
        if cancel_event and cancel_event.is_set():
            raise Exception("操作已取消")

        # 预处理：拆分多条语句
        statements = self.split_sql_statements(sql, progress_callback=progress_callback)
        if not statements:
            return [], [], 0, False, False, 0
            
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        try:
            # PostgreSQL: 在执行前设置 search_path
            if db_type != "MySQL" and schema:
                conn.run(f'SET search_path TO "{schema}"')
            
            total_affected = 0
            last_query_res = None
            total_stmts = len(statements)
            
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    try:
                        # 开启显式事务以提升大批量写入性能
                        cursor.execute("SET autocommit=0")
                        
                        # 极致动态步长：总数的 0.5%，范围锁定在 100 ~ 5000 之间
                        update_step = max(100, min(5000, total_stmts // 200))

                        # 合并连续同表 INSERT 为批量多行 VALUES，大幅减少 MySQL 网络往返
                        statements = self._batch_inserts(statements)
                        total_stmts = len(statements)
                        
                        for i, stmt in enumerate(statements):
                            if cancel_event and cancel_event.is_set():
                                raise Exception(f"批处理执行到第 {i+1} 条语句时被取消")
                            
                            if progress_callback and (i % update_step == 0 or i == total_stmts - 1):
                                pct = int(((i+1) / total_stmts) * 100)
                                progress_callback(pct, f"正在执行第 {i+1}/{total_stmts} 条语句...")

                            cursor.execute(stmt, params)
                            
                            # 捕获查询结果 (针对 SELECT 等)
                            if cursor.description:
                                columns = [col[0] for col in cursor.description]
                                raw_rows = cursor.fetchall()
                                # DictCursor 返回 dict_rows，转换为 list_rows 以匹配 API 契约
                                if raw_rows and isinstance(raw_rows[0], dict):
                                    rows = [[row.get(col) for col in columns] for row in raw_rows]
                                else:
                                    rows = raw_rows
                                truncated = False
                                total = len(rows)
                                if limit > 0:
                                    # 服务端分页
                                    rows = rows[offset:offset + limit]
                                last_query_res = (columns, rows, total, True, truncated, total)
                            else:
                                total_affected += cursor.rowcount
                        
                        conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                    finally:
                        cursor.execute("SET autocommit=1")
                    
                    if last_query_res:
                        return last_query_res
                    return ([], [], total_affected, False, False, 0)
            else:
                # PostgreSQL (pg8000.native)
                try:
                    conn.run("BEGIN")
                    # 同步极致动态步长逻辑
                    update_step = max(100, min(5000, total_stmts // 200))

                    for i, stmt in enumerate(statements):
                        if cancel_event and cancel_event.is_set():
                            raise Exception(f"批处理执行到第 {i+1} 条语句时被取消")

                        if progress_callback and (i % update_step == 0 or i == total_stmts - 1):
                            pct = int(((i+1) / total_stmts) * 100)
                            progress_callback(pct, f"正在执行第 {i+1}/{total_stmts} 条语句...")

                        if params:
                            if isinstance(params, dict):
                                rows = conn.run(stmt, **params)
                            else:
                                rows = conn.run(stmt, *params)
                        else:
                            rows = conn.run(stmt)

                        if hasattr(conn, 'columns') and conn.columns:
                            columns = [col['name'] for col in conn.columns]
                            # DictCursor 返回 dict_rows，转换为 list_rows
                            if rows and isinstance(rows[0], dict):
                                rows = [[row.get(col['name']) for col in conn.columns] for row in rows]
                            truncated = False
                            total = len(rows)
                            if limit > 0:
                                rows = rows[offset:offset + limit]
                            last_query_res = (columns, rows, total, True, truncated, total)
                    conn.run("COMMIT")

                    if last_query_res:
                        return last_query_res
                    return ([], [], total_affected, False, False, 0)
                except Exception:
                    conn.run("ROLLBACK")
                    raise
        finally:
            if hasattr(conn, 'close'): conn.close()

    def execute_batch_sql(self, conn_data, sql_list, database=None, cancel_event=None, schema=None):
        """
        在单个事务中执行多个 SQL 语句。
        sql_list: [(sql, params), (sql, params), ...]
        """
        db_type = conn_data.get('db_type', 'MySQL')
        conn = self.get_connection(conn_data, database=database)
        affected_total = 0
        try:
            # PostgreSQL: 在执行前设置 search_path
            if db_type != "MySQL" and schema:
                conn.run(f'SET search_path TO "{schema}"')
            
            if db_type == "MySQL":
                with conn.cursor() as cursor:
                    for sql, params in sql_list:
                        if cancel_event and cancel_event.is_set():
                            raise Exception("批处理已中途取消")
                        # 安全保护：将空字符串转为 None，避免与 DOUBLE/INT 列类型冲突
                        if params:
                            params = [None if p == '' else p for p in params]
                        affected_total += cursor.execute(sql, params)
                    conn.commit()
            else:
                # PostgreSQL
                for sql, params in sql_list:
                    if cancel_event and cancel_event.is_set():
                        raise Exception("批处理已中途取消")
                    if params:
                        if isinstance(params, dict):
                            conn.run(sql, **params)
                        else:
                            conn.run(sql, *params)
                    else:
                        conn.run(sql)
                    affected_total += 1
            return True, affected_total
        except Exception as e:
            if db_type == "MySQL": conn.rollback()
            return False, str(e)
        finally:
            if hasattr(conn, 'close'): conn.close()
