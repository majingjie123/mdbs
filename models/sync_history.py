import sqlite3
import json
import csv
import os
from datetime import datetime

class SyncHistoryManager:
    _db_path = "connections.db"

    @classmethod
    def save_record(cls, record_dict):
        """保存同步记录"""
        query = '''
            INSERT INTO sync_history (
                start_time, end_time, source_conn_id, source_db, 
                target_conn_id, target_db, tables, sync_structure, 
                sync_data, status, log_path, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            record_dict.get('start_time'),
            record_dict.get('end_time'),
            record_dict.get('source_conn_id'),
            record_dict.get('source_db'),
            record_dict.get('target_conn_id'),
            record_dict.get('target_db'),
            json.dumps(record_dict.get('tables', [])),
            1 if record_dict.get('sync_structure') else 0,
            1 if record_dict.get('sync_data') else 0,
            record_dict.get('status', 'running'),
            record_dict.get('log_path'),
            record_dict.get('error_summary')
        )
        with sqlite3.connect(cls._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def update_record(cls, record_id, update_dict):
        """更新同步记录（如结束时间、最终状态）"""
        fields = []
        params = []
        for key, value in update_dict.items():
            if key == 'tables':
                value = json.dumps(value)
            fields.append(f"{key}=?")
            params.append(value)
        
        params.append(record_id)
        query = f"UPDATE sync_history SET {', '.join(fields)} WHERE id=?"
        
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute(query, params)
            conn.commit()

    @classmethod
    def get_all_records(cls, limit=100):
        """获取所有同步历史"""
        query = '''
            SELECT h.*, s.name as source_name, t.name as target_name
            FROM sync_history h
            LEFT JOIN connections s ON h.source_conn_id = s.id
            LEFT JOIN connections t ON h.target_conn_id = t.id
            ORDER BY h.start_time DESC LIMIT ?
        '''
        with sqlite3.connect(cls._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @classmethod
    def get_record_by_id(cls, record_id):
        """获取单条记录详情"""
        with sqlite3.connect(cls._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sync_history WHERE id=?', (record_id,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res['tables'] = json.loads(res['tables']) if res['tables'] else []
                return res
            return None

    @classmethod
    def clear_history(cls):
        """清空历史记录"""
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute('DELETE FROM sync_history')
            conn.commit()

    @classmethod
    def export_to_csv(cls, filepath):
        """将历史记录导出为 CSV"""
        records = cls.get_all_records(limit=1000)
        if not records:
            return False
            
        keys = records[0].keys()
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(records)
        return True
