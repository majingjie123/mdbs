import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from core.db_operations import DBOperations
from models.db_storage import DBStorage
from core.theme import get_theme_colors
from core.ui_style import apply_navicat_style

class FunctionManagerDialog(tk.Toplevel):
    def __init__(self, parent, conn_id, db_name, func_name, func_type="FUNCTION"):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title(f"修改{'函数' if func_type=='FUNCTION' else '存储过程'} - {func_name}")
        self.resizable(True, True)

        # 居中
        width, height = 900, 650
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.transient(parent)
        self.grab_set()
        
        self.conn_id = conn_id
        self.db_name = db_name
        self.func_name = func_name
        self.func_type = func_type
        
        self.storage = DBStorage()
        self.db_ops = DBOperations()
        self.conn_data = self.storage.get_connection(conn_id)
        self.settings = self.storage.get_settings()
        
        self._init_ui()
        self._apply_theme()
        self._load_data()

    def _init_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_info = ttk.Frame(self.notebook)
        self.tab_params = ttk.Frame(self.notebook)
        self.tab_body = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_info, text=" 基本信息 ")
        self.notebook.add(self.tab_params, text=" 参数 ")
        self.notebook.add(self.tab_body, text=" 主体定义 ")
        
        self._setup_info_tab()
        self._setup_params_tab()
        self._setup_body_tab()

        # 底部按钮
        btn_frame = tk.Frame(self, padx=10, pady=10)
        btn_frame.pack(side="bottom", fill="x")
        
        ttk.Button(btn_frame, text="执行修改", command=self._save_changes, style="Navicat.Primary.TButton").pack(side="right", padx=5)
        ttk.Button(btn_frame, text="预览 SQL", command=self._preview_sql, style="Navicat.Primary.TButton").pack(side="right", padx=5)
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side="right", padx=5)

    def _setup_info_tab(self):
        self.info_vars = {}
        fields = [("名称:", "ROUTINE_NAME"), ("返回类型:", "DATA_TYPE"), ("语言:", "EXTERNAL_LANGUAGE"), ("确定性:", "IS_DETERMINISTIC"), ("SQL 访问:", "SQL_DATA_ACCESS")]
        
        frame = tk.Frame(self.tab_info, padx=20, pady=20)
        frame.pack(fill="both", expand=True)
        
        for i, (label, key) in enumerate(fields):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", pady=5)
            var = tk.StringVar()
            self.info_vars[key] = var
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky="w", padx=10, pady=5)
            if key == "ROUTINE_NAME": entry.configure(state="readonly")

    def _setup_params_tab(self):
        toolbar = tk.Frame(self.tab_params)
        toolbar.pack(side="top", fill="x", padx=5, pady=2)
        
        ttk.Button(toolbar, text="+ 添加参数", command=self._add_param).pack(side="left", padx=2)
        ttk.Button(toolbar, text="- 删除参数", command=self._delete_param).pack(side="left", padx=2)

        cols = ("mode", "name", "type")
        self.param_tree = ttk.Treeview(self.tab_params, columns=cols, show="headings")
        self.param_tree.heading("mode", text="模式 (IN/OUT/INOUT)")
        self.param_tree.heading("name", text="参数名")
        self.param_tree.heading("type", text="数据类型")
        
        self.param_tree.pack(fill="both", expand=True)
        self.param_tree.bind("<Double-1>", self._on_param_double_click)

    def _setup_body_tab(self):
        self.body_editor = tk.Text(self.tab_body, font=("Consolas", 11), undo=True)
        self.body_editor.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_data(self):
        def run():
            try:
                data = self.db_ops.get_function_metadata(self.conn_data, self.func_name, database=self.db_name)
                ddl = self.db_ops.get_function_ddl(self.conn_data, self.func_name, func_type=self.func_type, database=self.db_name)
                self.after(0, lambda: self._update_ui_data(data, ddl))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("错误", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _update_ui_data(self, data, ddl):
        if data.get('info'):
            info = data['info']
            for k, v in self.info_vars.items():
                v.set(str(info.get(k, '')))
        
        if data.get('params'):
            for p in data['params']:
                self.param_tree.insert("", "end", values=(p.get('PARAMETER_MODE', 'IN'), p.get('PARAMETER_NAME', ''), p.get('DTD_IDENTIFIER', '')))
        
        # 提取主体定义 (此处简化，直接显示完整 DDL 供修改，或解析主体)
        self.body_editor.insert("1.0", ddl)

    def _on_param_double_click(self, event):
        item = self.param_tree.identify_row(event.y)
        column = self.param_tree.identify_column(event.x)
        if not item or not column: return
        
        col_idx = int(column[1:]) - 1
        curr_vals = list(self.param_tree.item(item, "values"))
        
        new_val = simpledialog.askstring("编辑", "修改:", initialvalue=curr_vals[col_idx], parent=self)
        if new_val is not None:
            curr_vals[col_idx] = new_val
            self.param_tree.item(item, values=curr_vals)

    def _add_param(self):
        self.param_tree.insert("", "end", values=("IN", "new_param", "VARCHAR(255)"))

    def _delete_param(self):
        sel = self.param_tree.selection()
        if sel: self.param_tree.delete(sel)

    def _generate_sql(self):
        # 简单处理：如果用户修改了 DDL，直接返回 DDL
        # 真正的修改通常是 DROP + CREATE
        return self.body_editor.get("1.0", tk.END).strip()

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
        tk.Text(preview_win, padx=10, pady=10).pack(fill="both", expand=True)
        preview_win.children['!text'].insert("1.0", sql)

    def _save_changes(self):
        sql = self._generate_sql()
        if not sql: return
        if not messagebox.askyesno("确认", "确定执行修改？(通常会先执行 DROP 再 CREATE)"): return
        
        def run():
            try:
                # 为了安全，先执行 DROP
                db_type = self.conn_data.get('db_type', 'MySQL')
                drop_sql = f"DROP {self.func_type} IF EXISTS `{self.func_name}`"
                if db_type != "MySQL": drop_sql = f'DROP {self.func_type} IF EXISTS "{self.func_name}"'
                
                batch = [(drop_sql, None), (sql, None)]
                success, msg = self.db_ops.execute_batch_sql(self.conn_data, batch, database=self.db_name)
                if success:
                    self.after(0, lambda: messagebox.showinfo("成功", "已更新"))
                    self.after(0, self.destroy)
                else:
                    self.after(0, lambda: messagebox.showerror("失败", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("错误", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _apply_theme(self):
        theme = self.settings.get('theme', '默认')
        colors = get_theme_colors(theme)
        bg, fg, hb = colors["bg"], colors["fg"], colors["hb"]

        # 应用背景到顶层窗口
        self.configure(bg=bg)

        # 应用背景到各个选项卡（tk.Frame）
        for tab in (self.tab_info, self.tab_params, self.tab_body):
            try:
                for child in tab.winfo_children():
                    if isinstance(child, (tk.Frame, tk.Label)):
                        child.configure(bg=bg, fg=fg)
                    elif isinstance(child, tk.Text):
                        child.configure(bg=bg, fg=fg, insertbackground=fg)
            except: pass

        # 主体编辑器
        self.body_editor.configure(bg=bg, fg=fg, insertbackground=fg)

        # 底部按钮区域
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w != self.notebook:
                w.configure(bg=bg)
                for c in w.winfo_children():
                    if isinstance(c, ttk.Button):
                        pass  # ttk.Button 由 style 控制
                    elif isinstance(c, tk.Frame):
                        c.configure(bg=bg)

        # ttk 样式
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except: pass
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)

        # 预览窗口（如果打开）
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                try:
                    child.configure(bg=bg)
                    for c in child.winfo_children():
                        if isinstance(c, tk.Text):
                            c.configure(bg=bg, fg=fg, insertbackground=fg)
                except: pass
