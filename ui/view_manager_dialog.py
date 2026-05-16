import tkinter as tk
from tkinter import ttk, messagebox
import threading
from core.db_operations import DBOperations
from models.db_storage import DBStorage
from core.theme import get_theme_colors
from core.ui_style import apply_navicat_style
from ui.sql_workbench import SQLWorkbench

class ViewManagerDialog(tk.Toplevel):
    def __init__(self, parent, conn_id, db_name, view_name):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title(f"修改视图 - {view_name}")
        self.resizable(True, True)

        # 居中
        width, height = 900, 600
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.transient(parent)
        self.grab_set()
        
        self.conn_id = conn_id
        self.db_name = db_name
        self.view_name = view_name
        
        self.storage = DBStorage()
        self.db_ops = DBOperations()
        self.conn_data = self.storage.get_connection(conn_id)
        self.settings = self.storage.get_settings()
        
        self._init_ui()
        self._apply_theme()
        self._load_definition()

    def _init_ui(self):
        # 顶部信息
        info_frame = tk.Frame(self, padx=10, pady=5)
        info_frame.pack(side="top", fill="x")
        tk.Label(info_frame, text=f"视图: {self.view_name} (库: {self.db_name})", font=("Microsoft YaHei", 9, "bold")).pack(side="left")

        # SQL 编辑器 (复用 SQLWorkbench 的编辑器逻辑或简单实现)
        # 此处我们创建一个带滚动条的 Text
        self.editor_frame = tk.Frame(self)
        self.editor_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.editor = tk.Text(self.editor_frame, font=("Consolas", 11), undo=True)
        self.editor.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(self.editor_frame, command=self.editor.yview)
        self.editor.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # 底部按钮
        btn_frame = tk.Frame(self, padx=10, pady=10)
        btn_frame.pack(side="bottom", fill="x")
        
        ttk.Button(btn_frame, text="执行修改", command=self._save_changes, style="Navicat.Primary.TButton").pack(side="right", padx=5)
        ttk.Button(btn_frame, text="预览 SQL", command=self._preview_sql, style="Navicat.Primary.TButton").pack(side="right", padx=5)
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side="right", padx=5)

    def _load_definition(self):
        def run():
            try:
                ddl = self.db_ops.get_view_ddl(self.conn_data, self.view_name, database=self.db_name)
                self.after(0, lambda: self.editor.insert("1.0", ddl))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", f"加载视图定义失败: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _generate_sql(self):
        return self.editor.get("1.0", tk.END).strip()

    def _preview_sql(self):
        sql = self._generate_sql()
        if not sql: return
        
        preview_win = tk.Toplevel(self)
        preview_win.title("SQL 预览")
        preview_win.resizable(False, False)
        width, height = 600, 400
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        preview_win.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        
        text = tk.Text(preview_win, padx=10, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("1.0", sql)
        
        ttk.Button(preview_win, text="确定", command=preview_win.destroy).pack(pady=5)

    def _save_changes(self):
        sql = self._generate_sql()
        if not sql: return
        
        if not messagebox.askyesno("确认", "确定执行该视图定义修改？"):
            return
            
        def run():
            try:
                # 视图修改通常是 CREATE OR REPLACE VIEW
                success, affected = self.db_ops.execute_sql(self.conn_data, sql, database=self.db_name)
                # execute_sql 返回 (cols, rows, affected, is_query)
                self.after(0, lambda: messagebox.showinfo("成功", "视图已更新"))
                self.after(0, self.destroy)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("修改失败", str(e)))
                
        threading.Thread(target=run, daemon=True).start()

    def _apply_theme(self):
        theme = self.settings.get('theme', '默认')
        colors = get_theme_colors(theme)
        bg, fg = colors["bg"], colors["fg"]

        self.configure(bg=bg)
        self.editor.configure(bg=bg, fg=fg, insertbackground=fg)

        # 信息区域
        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=bg)
                for c in child.winfo_children():
                    if isinstance(c, tk.Label):
                        c.configure(bg=bg, fg=fg)
                    elif isinstance(c, tk.Text):
                        c.configure(bg=bg, fg=fg, insertbackground=fg)

        # 预览窗口（如果打开）
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                try:
                    child.configure(bg=bg)
                    for c in child.winfo_children():
                        if isinstance(c, tk.Text):
                            c.configure(bg=bg, fg=fg, insertbackground=fg)
                        elif isinstance(c, tk.Frame):
                            c.configure(bg=bg)
                except: pass

        style = ttk.Style()
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
