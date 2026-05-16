import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from core.db_operations import DBOperations
from models.db_storage import DBStorage
from core.theme import get_theme_colors
from core.ui_style import apply_navicat_style

class TableManagerDialog(tk.Toplevel):
    def __init__(self, parent, conn_id, db_name, table_name, read_only=True):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title(f"{'查询' if read_only else '修改'}表结构 - {table_name}")
        
        self.storage = DBStorage()
        # 恢复尺寸
        geom = self.storage.get_geometry("table_manager")
        if geom:
            self.geometry(geom)
        else:
            width, height = 950, 680
            x = (self.winfo_screenwidth() / 2) - (width / 2)
            y = (self.winfo_screenheight() / 2) - (height / 2)
            self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.conn_id = conn_id
        self.db_name = db_name
        self.table_name = table_name
        self.read_only = read_only
        
        self.storage = DBStorage()
        self.db_ops = DBOperations()
        self.conn_data = self.storage.get_connection(conn_id)
        self.settings = self.storage.get_settings()
        
        self.original_columns = []
        self.original_indexes = []
        self.original_options = {}
        
        self._init_ui()
        self._apply_theme()
        self._load_data()

    def _on_close(self):
        """关闭时保存尺寸"""
        try:
            self.storage.save_geometry("table_manager", self.geometry())
        except: pass
        self.destroy()

    def _init_ui(self):
        # 顶部信息栏
        info_frame = tk.Frame(self, padx=10, pady=5)
        info_frame.pack(side="top", fill="x")
        tk.Label(info_frame, text=f"连接: {self.conn_data['name']}  |  数据库: {self.db_name}  |  表: {self.table_name}", font=("Microsoft YaHei", 9, "bold")).pack(side="left")

        # 中间选项卡
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_columns = ttk.Frame(self.notebook)
        self.tab_indexes = ttk.Frame(self.notebook)
        self.tab_options = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_columns, text=" 字段 ")
        self.notebook.add(self.tab_indexes, text=" 索引 ")
        self.notebook.add(self.tab_options, text=" 选项 ")
        
        self._setup_columns_tab()
        self._setup_indexes_tab()
        self._setup_options_tab()

        # 底部按钮
        btn_frame = tk.Frame(self, padx=10, pady=10)
        btn_frame.pack(side="bottom", fill="x")
        
        ttk.Button(btn_frame, text="刷新", command=self._load_data).pack(side="left", padx=5)
        
        if not self.read_only:
            # 权限检查：简单模拟
            is_readonly = 'read' in self.conn_data['user'].lower()
            if is_readonly:
                btn_save = ttk.Button(btn_frame, text="执行修改 (无权限)", state="disabled")
                btn_save.pack(side="right", padx=5)
            else:
                ttk.Button(btn_frame, text="执行修改", command=self._save_changes, style="Navicat.Primary.TButton").pack(side="right", padx=5)
                ttk.Button(btn_frame, text="预览 SQL", command=self._preview_sql, style="Navicat.Primary.TButton").pack(side="right", padx=5)
        
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side="right", padx=5)

    def _setup_columns_tab(self):
        toolbar = tk.Frame(self.tab_columns)
        toolbar.pack(side="top", fill="x", padx=5, pady=2)
        
        if not self.read_only:
            ttk.Button(toolbar, text="+ 添加字段", command=self._add_column_row).pack(side="left", padx=2)
            ttk.Button(toolbar, text="- 删除字段", command=self._delete_column_row).pack(side="left", padx=2)
            ttk.Button(toolbar, text="↑ 上移", command=lambda: self._move_row(-1)).pack(side="left", padx=2)
            ttk.Button(toolbar, text="↓ 下移", command=lambda: self._move_row(1)).pack(side="left", padx=2)

        cols = ("name", "type", "null", "key", "default", "comment")
        self.col_tree = ttk.Treeview(self.tab_columns, columns=cols, show="headings", selectmode="browse")
        self.col_tree.heading("name", text="字段名")
        self.col_tree.heading("type", text="数据类型")
        self.col_tree.heading("null", text="允许NULL")
        self.col_tree.heading("key", text="键类型")
        self.col_tree.heading("default", text="默认值")
        self.col_tree.heading("comment", text="注释")
        
        for c in cols: self.col_tree.column(c, width=120)
        self.col_tree.column("comment", width=200)
        
        self.col_tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(self.tab_columns, orient="vertical", command=self.col_tree.yview)
        self.col_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
        if not self.read_only:
            self.col_tree.bind("<Double-1>", self._on_col_double_click)

    def _setup_indexes_tab(self):
        toolbar = tk.Frame(self.tab_indexes)
        toolbar.pack(side="top", fill="x", padx=5, pady=2)
        
        if not self.read_only:
            ttk.Button(toolbar, text="+ 添加索引", command=self._add_index_row).pack(side="left", padx=2)
            ttk.Button(toolbar, text="- 删除索引", command=self._delete_index_row).pack(side="left", padx=2)

        cols = ("name", "columns", "unique", "type", "comment")
        self.idx_tree = ttk.Treeview(self.tab_indexes, columns=cols, show="headings")
        self.idx_tree.heading("name", text="索引名")
        self.idx_tree.heading("columns", text="包含列")
        self.idx_tree.heading("unique", text="唯一")
        self.idx_tree.heading("type", text="索引类型")
        self.idx_tree.heading("comment", text="注释")
        
        for c in cols: self.idx_tree.column(c, width=150)
        self.idx_tree.pack(fill="both", expand=True)
        
        if not self.read_only:
            self.idx_tree.bind("<Double-1>", self._on_idx_double_click)

    def _setup_options_tab(self):
        self.opt_frame = tk.Frame(self.tab_options, padx=20, pady=20)
        self.opt_frame.pack(fill="both", expand=True)
        
        self.opt_vars = {}
        opts = [("表注释:", "Comment"), ("引擎:", "Engine"), ("字符集:", "Collation"), ("自增起始:", "Auto_increment")]
        
        for i, (label, key) in enumerate(opts):
            tk.Label(self.opt_frame, text=label).grid(row=i, column=0, sticky="e", pady=5)
            var = tk.StringVar()
            self.opt_vars[key] = var
            entry = ttk.Entry(self.opt_frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky="w", padx=10, pady=5)
            if self.read_only: entry.configure(state="readonly")

    def _load_data(self):
        def run():
            try:
                cols = self.db_ops.get_table_columns_detailed(self.conn_data, self.table_name, self.db_name)
                idxs = self.db_ops.get_table_indexes_detailed(self.conn_data, self.table_name, self.db_name)
                opts = self.db_ops.get_table_options_detailed(self.conn_data, self.table_name, self.db_name)
                
                self.after(0, lambda: self._update_ui_data(cols, idxs, opts))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", f"加载表结构失败: {e}"))
        
        threading.Thread(target=run, daemon=True).start()

    def _update_ui_data(self, cols, idxs, opts):
        # 字段
        for item in self.col_tree.get_children(): self.col_tree.delete(item)
        self.original_columns = []
        for c in cols:
            vals = (c['Field'], c['Type'], c['Null'], c['Key'], c.get('Default', ''), c.get('Comment', ''))
            self.col_tree.insert("", "end", values=vals)
            self.original_columns.append(dict(c))
            
        # 索引
        for item in self.idx_tree.get_children(): self.idx_tree.delete(item)
        self.original_indexes = idxs
        # 聚合索引列
        idx_map = {}
        for x in idxs:
            name = x['Key_name']
            if name not in idx_map:
                idx_map[name] = {
                    'name': name,
                    'columns': [],
                    'unique': "YES" if x['Non_unique'] == 0 else "NO",
                    'type': x.get('Index_type', ''),
                    'comment': x.get('Index_comment', '')
                }
            idx_map[name]['columns'].append(x['Column_name'])
        
        for name, data in idx_map.items():
            self.idx_tree.insert("", "end", values=(name, ", ".join(data['columns']), data['unique'], data['type'], data['comment']))
            
        # 选项
        self.original_options = opts if opts else {}
        for key, var in self.opt_vars.items():
            val = self.original_options.get(key, '')
            if val is None: val = ''
            var.set(str(val))

    def _on_col_double_click(self, event):
        if self.read_only: return
        item = self.col_tree.identify_row(event.y)
        column = self.col_tree.identify_column(event.x)
        if not item or not column: return
        
        col_idx = int(column[1:]) - 1
        curr_vals = list(self.col_tree.item(item, "values"))
        col_name = self.col_tree.heading(column)['text']
        
        # 弹窗编辑
        edit_win = tk.Toplevel(self)
        edit_win.title(f"编辑 {col_name}")
        edit_win.geometry("300x150")
        edit_win.transient(self)
        edit_win.grab_set()
        
        tk.Label(edit_win, text=f"修改 {col_name}:", pady=10).pack()
        
        db_type = self.conn_data.get('db_type', 'MySQL')
        val_var = tk.StringVar(value=curr_vals[col_idx])
        
        entry = None
        if col_name == "数据类型":
            types = ["INT", "VARCHAR(255)", "TEXT", "DATETIME", "DECIMAL(10,2)", "TINYINT"]
            if db_type != "MySQL": types = ["INTEGER", "VARCHAR", "TEXT", "TIMESTAMP", "NUMERIC", "BOOLEAN"]
            entry = ttk.Combobox(edit_win, textvariable=val_var, values=types)
        elif col_name == "允许NULL":
            entry = ttk.Combobox(edit_win, textvariable=val_var, values=["YES", "NO"], state="readonly")
        elif col_name == "键类型":
            entry = ttk.Combobox(edit_win, textvariable=val_var, values=["", "PRI", "UNI"], state="readonly")
        elif col_name == "默认值":
            entry = ttk.Combobox(edit_win, textvariable=val_var, values=["NULL", "CURRENT_TIMESTAMP", "''"])
        else:
            entry = ttk.Entry(edit_win, textvariable=val_var)
            
        entry.pack(padx=20, fill="x")
        entry.focus_set()
        
        def save():
            curr_vals[col_idx] = val_var.get()
            self.col_tree.item(item, values=curr_vals)
            edit_win.destroy()
            
        ttk.Button(edit_win, text="确定", command=save).pack(pady=10)
        edit_win.bind("<Return>", lambda e: save())
        edit_win.bind("<Escape>", lambda e: edit_win.destroy())

    def _on_idx_double_click(self, event):
        if self.read_only: return
        # 索引编辑逻辑可根据需要实现，目前仅提供基础占位
        pass

    def _add_column_row(self):
        self.col_tree.insert("", "end", values=("new_column", "varchar(255)", "YES", "", "", ""))

    def _delete_column_row(self):
        sel = self.col_tree.selection()
        if sel: 
            if messagebox.askyesno("确认", "确定删除该字段？"):
                self.col_tree.delete(sel)

    def _move_row(self, direction):
        sel = self.col_tree.selection()
        if not sel: return
        idx = self.col_tree.index(sel[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.col_tree.get_children()):
            self.col_tree.move(sel[0], "", new_idx)

    def _add_index_row(self):
        self.idx_tree.insert("", "end", values=("idx_new", "column1", "NO", "BTREE", ""))

    def _delete_index_row(self):
        sel = self.idx_tree.selection()
        if sel: self.idx_tree.delete(sel)

    def _generate_alter_sql(self):
        db_type = self.conn_data.get('db_type', 'MySQL')
        sqls = []
        
        curr_cols = []
        for item in self.col_tree.get_children():
            v = self.col_tree.item(item, "values")
            curr_cols.append({
                'Field': v[0], 'Type': v[1], 'Null': v[2], 'Key': v[3], 'Default': v[4], 'Comment': v[5]
            })
            
        orig_map = {c['Field']: c for c in self.original_columns}
        curr_names = [c['Field'] for c in curr_cols]
        
        if db_type == "MySQL":
            # 删除字段
            for name in orig_map:
                if name not in curr_names:
                    sqls.append(f"ALTER TABLE `{self.table_name}` DROP COLUMN `{name}`;")
            
            # 添加/修改字段
            for i, c in enumerate(curr_cols):
                null_stmt = "NULL" if c['Null'] == "YES" else "NOT NULL"
                default_stmt = f"DEFAULT '{c['Default']}'" if c['Default'] and c['Default'] != 'NULL' else ""
                if c['Default'] == 'NULL': default_stmt = "DEFAULT NULL"
                comment_stmt = f"COMMENT '{c['Comment']}'" if c['Comment'] else ""
                
                if c['Field'] not in orig_map:
                    after = f" AFTER `{curr_cols[i-1]['Field']}`" if i > 0 else " FIRST"
                    sqls.append(f"ALTER TABLE `{self.table_name}` ADD COLUMN `{c['Field']}` {c['Type']} {null_stmt} {default_stmt} {comment_stmt}{after};")
                else:
                    orig = orig_map[c['Field']]
                    if (orig['Type'] != c['Type'] or orig['Null'] != c['Null'] or 
                        str(orig.get('Default', '')) != str(c['Default']) or 
                        orig.get('Comment', '') != c['Comment']):
                        sqls.append(f"ALTER TABLE `{self.table_name}` MODIFY COLUMN `{c['Field']}` {c['Type']} {null_stmt} {default_stmt} {comment_stmt};")
        else:
            # PostgreSQL
            for name in orig_map:
                if name not in curr_names:
                    sqls.append(f'ALTER TABLE "{self.table_name}" DROP COLUMN "{name}";')
            
            for c in curr_cols:
                if c['Field'] not in orig_map:
                    sqls.append(f'ALTER TABLE "{self.table_name}" ADD COLUMN "{c['Field']}" {c['Type']};')
                    if c['Null'] == "NO":
                        sqls.append(f'ALTER TABLE "{self.table_name}" ALTER COLUMN "{c['Field']}" SET NOT NULL;')
                    if c['Comment']:
                        sqls.append(f'COMMENT ON COLUMN "{self.table_name}"."{c['Field']}" IS \'{c['Comment']}\';')
                else:
                    orig = orig_map[c['Field']]
                    if orig['Type'] != c['Type']:
                        sqls.append(f'ALTER TABLE "{self.table_name}" ALTER COLUMN "{c['Field']}" TYPE {c['Type']};')
                    if orig['Null'] != c['Null']:
                        action = "SET" if c['Null'] == "NO" else "DROP"
                        sqls.append(f'ALTER TABLE "{self.table_name}" ALTER COLUMN "{c['Field']}" {action} NOT NULL;')
                    if orig.get('Comment', '') != c['Comment']:
                        sqls.append(f'COMMENT ON COLUMN "{self.table_name}"."{c['Field']}" IS \'{c['Comment']}\';')
                
        return sqls

    def _preview_sql(self):
        sqls = self._generate_alter_sql()
        if not sqls:
            messagebox.showinfo("信息", "未检测到任何变更")
            return
            
        preview_win = tk.Toplevel(self)
        preview_win.title("SQL 预览")
        preview_win.geometry("600x400")
        
        text = tk.Text(preview_win, padx=10, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("1.0", "\n".join(sqls))
        
        ttk.Button(preview_win, text="复制 SQL", command=lambda: self._copy_to_clipboard("\n".join(sqls))).pack(pady=5)

    def _copy_to_clipboard(self, content):
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("成功", "已复制到剪贴板")

    def _save_changes(self):
        sqls = self._generate_alter_sql()
        if not sqls:
            messagebox.showinfo("信息", "未检测到任何变更")
            return
            
        if not messagebox.askyesno("确认", "确定执行以上 SQL 变更？"):
            return
            
        def run():
            try:
                batch = [(sql, None) for sql in sqls]
                success, msg = self.db_ops.execute_batch_sql(self.conn_data, batch, self.db_name)
                if success:
                    self.after(0, lambda: messagebox.showinfo("成功", "表结构修改已执行"))
                    self.after(0, self._load_data)
                else:
                    self.after(0, lambda: messagebox.showerror("执行失败", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("错误", str(e)))
                
        threading.Thread(target=run, daemon=True).start()

    def _apply_theme(self):
        theme = self.settings.get('theme', '默认')
        colors = get_theme_colors(theme)
        bg, fg, hb = colors["bg"], colors["fg"], colors["hb"]

        self.configure(bg=bg)
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except: pass
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg)
        style.configure("Treeview.Heading", background=hb, foreground=fg)

        self._update_all_tk_bg(self, bg, fg)

    def _update_all_tk_bg(self, parent, color, fg="#333333"):
        try:
            if isinstance(parent, (tk.Toplevel, tk.Frame, tk.Label, ttk.Frame)):
                parent.configure(bg=color)
            if isinstance(parent, (tk.Label, tk.Text, tk.Entry, tk.Listbox)):
                parent.configure(fg=fg)
            if isinstance(parent, tk.Text):
                parent.configure(bg=color, insertbackground=fg)
        except: pass
        for child in parent.winfo_children():
            self._update_all_tk_bg(child, color, fg)
