import os
import time
from datetime import datetime

class ScratchManager:
    _base_dir = os.path.join(os.path.expanduser("~"), ".db_connector_scratch")

    def __init__(self):
        if not os.path.exists(self._base_dir):
            os.makedirs(self._base_dir)

    def _get_db_dir(self, conn_name, db_name):
        """获取特定连接和库的专用目录"""
        # 清理非法路径字符
        def safe_name(n): return "".join([c for c in n if c.isalnum() or c in (' ', '_', '-')]).strip()
        path = os.path.join(self._base_dir, safe_name(conn_name), safe_name(db_name))
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def save_autosave(self, identifier, content):
        """自动保存草稿 (identifier 通常是 conn_name_db_name)"""
        filename = f"autosave_{identifier}.sql"
        filepath = os.path.join(self._base_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def load_autosave(self, identifier):
        """加载自动保存的草稿"""
        filename = f"autosave_{identifier}.sql"
        filepath = os.path.join(self._base_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def save_script(self, conn_name, db_name, title, content):
        """保存正式脚本到对应的库线下"""
        target_dir = self._get_db_dir(conn_name, db_name)
        # 清理标题
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_title: safe_title = "untitled"
        
        filename = f"{safe_title}.sql"
        filepath = os.path.join(target_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def list_scripts(self, conn_name=None, db_name=None):
        """列出脚本。如果提供了连接名和库名，则仅列出该路径下的"""
        if conn_name and db_name:
            target_dir = self._get_db_dir(conn_name, db_name)
            scripts = []
            if os.path.exists(target_dir):
                for f in os.listdir(target_dir):
                    if f.endswith(".sql"):
                        path = os.path.join(target_dir, f)
                        scripts.append({
                            'name': f.replace(".sql", ""),
                            'path': path,
                            'filename': f,
                            'mtime': os.path.getmtime(path)
                        })
            return sorted(scripts, key=lambda x: x['mtime'], reverse=True)
        else:
            # 兼容旧逻辑或全局列出 (递归搜索)
            all_scripts = []
            for root, dirs, files in os.walk(self._base_dir):
                for f in files:
                    if f.endswith(".sql") and not f.startswith("autosave_"):
                        path = os.path.join(root, f)
                        all_scripts.append({
                            'name': f,
                            'path': path,
                            'mtime': os.path.getmtime(path)
                        })
            return sorted(all_scripts, key=lambda x: x['mtime'], reverse=True)

    def delete_script_path(self, filepath):
        if os.path.exists(filepath):
            os.remove(filepath)

    def rename_script(self, old_path, new_title):
        """重命名脚本文件"""
        if not os.path.exists(old_path): return False
        
        target_dir = os.path.dirname(old_path)
        # 清理新标题
        safe_title = "".join([c for c in new_title if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_title: return False
        
        new_path = os.path.join(target_dir, f"{safe_title}.sql")
        if os.path.exists(new_path):
            return False # 已存在同名文件
            
        try:
            os.rename(old_path, new_path)
            return True
        except:
            return False

    def get_script_content_by_path(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return ""
