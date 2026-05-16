"""
数据导入对话框（CSV / Excel）
遵循 ui/export_dialog.py 的 tk.Toplevel 模式。
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from models.db_storage import DBStorage
from core.db_operations import DBOperations
from core.importer import Importer
from ui.progress_dialog import ProgressDialog
from core.ui_style import apply_navicat_style


class ImportDialog(tk.Toplevel):
    def __init__(self, parent, conn_data=None, database=None, schema=None, table_name=None):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title("📥 数据导入向导")
        self.resizable(True, True)
        self.minsize(620, 500)

        self._base_width = 620
        self._base_height = 520

        # 居中
        x = (self.winfo_screenwidth() / 2) - (self._base_width / 2)
        y = (self.winfo_screenheight() / 2) - (self._base_height / 2)
        self.geometry(f'{self._base_width}x{self._base_height}+{int(x)}+{int(y)}')

        self.storage = DBStorage()
        self.db_ops = DBOperations()
        self.all_connections = self.storage.get_all_connections()

        # 解析后的数据缓存
        self._parsed_columns = []
        self._parsed_rows_display = []
        self._parsed_rows_raw = []
        self._file_path = None

        self._prefill_conn = conn_data
        self._prefill_db = database
        self._prefill_schema = schema
        self._prefill_table = table_name

        self._init_ui()
        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        self.main_frame = ttk.Frame(self, padding=15)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=1)

        # ── 第一步：选择文件 ──
        ttk.Label(self.main_frame, text="第一步: 选择数据文件",
                  font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))

        file_sel_frame = ttk.Frame(self.main_frame)
        file_sel_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_sel_frame.columnconfigure(1, weight=1)

        self.lbl_file = ttk.Label(file_sel_frame, text="未选择文件", foreground="gray")
        self.lbl_file.grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Button(file_sel_frame, text="浏览...", command=self._browse_file).grid(row=0, column=1, sticky="e")

        # ── 文件选项 ──
        options_frame = ttk.Frame(self.main_frame)
        options_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)
        options_frame.columnconfigure(3, weight=1)

        ttk.Label(options_frame, text="分隔符:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.cb_delimiter = ttk.Combobox(options_frame, values=[",", ";", "\\t", "|"], width=6, state="readonly")
        self.cb_delimiter.set(",")
        self.cb_delimiter.grid(row=0, column=1, sticky="w", padx=(0, 15))

        self.has_header_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="首行为列名", variable=self.has_header_var,
                        command=self._on_options_changed).grid(row=0, column=2, sticky="w", padx=(0, 15))

        ttk.Label(options_frame, text="编码:").grid(row=0, column=4, sticky="w", padx=(0, 4))
        self.cb_encoding = ttk.Combobox(options_frame, values=["自动检测", "utf-8", "gbk", "utf-8-sig"], width=10, state="readonly")
        self.cb_encoding.set("自动检测")
        self.cb_encoding.grid(row=0, column=5, sticky="w")

        # ── 预览区域 ──
        ttk.Label(self.main_frame, text="第二步: 预览数据（前 20 行）",
                  font=("Microsoft YaHei", 10, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 5))

        preview_container = ttk.Frame(self.main_frame)
        preview_container.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        preview_container.rowconfigure(0, weight=1)
        preview_container.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(4, weight=1)

        self.tree_preview = ttk.Treeview(preview_container, show="headings", height=8)
        vsb = ttk.Scrollbar(preview_container, orient="vertical", command=self.tree_preview.yview)
        hsb = ttk.Scrollbar(preview_container, orient="horizontal", command=self.tree_preview.xview)
        self.tree_preview.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree_preview.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        preview_info = ttk.Frame(self.main_frame)
        preview_info.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self.lbl_preview_info = ttk.Label(preview_info, text="共 0 行，0 列", foreground="gray")
        self.lbl_preview_info.pack(side="left")

        # ── 第三步：数据库目标和模式 ──
        ttk.Label(self.main_frame, text="第三步: 目标数据库与表",
                  font=("Microsoft YaHei", 10, "bold")).grid(row=6, column=0, sticky="w", pady=(0, 5))

        target_frame = ttk.Frame(self.main_frame)
        target_frame.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        target_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(3, weight=1)
        target_frame.columnconfigure(5, weight=1)

        ttk.Label(target_frame, text="连接:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.cb_conn = ttk.Combobox(target_frame, values=[c['name'] for c in self.all_connections],
                                    state="readonly", width=16)
        self.cb_conn.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.cb_conn.bind("<<ComboboxSelected>>", self._on_conn_selected)

        ttk.Label(target_frame, text="数据库:").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.cb_db = ttk.Combobox(target_frame, values=[], state="readonly", width=16)
        self.cb_db.grid(row=0, column=3, sticky="ew", padx=(0, 8))
        self.cb_db.bind("<<ComboboxSelected>>", self._on_db_selected)

        self.lbl_schema = ttk.Label(target_frame, text="Schema:")
        self.cb_schema = ttk.Combobox(target_frame, values=[], state="readonly", width=10)

        ttk.Label(target_frame, text="表名:").grid(row=0, column=4, sticky="w", padx=(0, 4))
        self.cb_table = ttk.Combobox(target_frame, values=[], width=16)
        self.cb_table.grid(row=0, column=5, sticky="ew")

        # ── 导入模式 ──
        mode_frame = ttk.Frame(self.main_frame)
        mode_frame.grid(row=8, column=0, sticky="ew", pady=(0, 10))

        self.import_mode = tk.StringVar(value="append")
        ttk.Radiobutton(mode_frame, text="追加 (INSERT)", variable=self.import_mode,
                        value="append").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(mode_frame, text="清空并导入 (REPLACE)", variable=self.import_mode,
                        value="replace").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(mode_frame, text="新建表 (CREATE)", variable=self.import_mode,
                        value="create").pack(side="left")

        # ── 底部按钮 ──
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.grid(row=10, column=0, sticky="ew", pady=(10, 0))

        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=5)
        self.btn_start = ttk.Button(btn_frame, text="开始导入", command=self._start_import, state="disabled", style="Navicat.Primary.TButton")
        self.btn_start.pack(side="right", padx=5)

        # 预填值
        if self._prefill_conn:
            conn_name = self._prefill_conn.get('name', '')
            for i, c in enumerate(self.all_connections):
                if c.get('id') == self._prefill_conn.get('id') or c['name'] == conn_name:
                    self.cb_conn.current(i)
                    self._on_conn_selected(None)
                    break
            if self._prefill_db:
                self.cb_db.set(self._prefill_db)
                self._on_db_selected(None)
            if self._prefill_schema and self.lbl_schema.winfo_ismapped():
                self.cb_schema.set(self._prefill_schema)
            if self._prefill_table:
                self.cb_table.set(self._prefill_table)

    def _browse_file(self):
        file_path = filedialog.askopenfilename(
            title="选择数据文件",
            filetypes=[("CSV 文件", "*.csv"), ("Excel 文件", "*.xlsx;*.xls"),
                       ("所有文件", "*.*")]
        )
        if not file_path:
            return
        self._file_path = file_path
        self.lbl_file.config(text=os.path.basename(file_path), foreground="black")

        # 自动切换分隔符和编码选项
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.xlsx', '.xls'):
            self.cb_delimiter.config(state="disabled")
            self.cb_encoding.config(state="disabled")
        else:
            self.cb_delimiter.config(state="readonly")
            self.cb_encoding.config(state="readonly")

        self._parse_and_preview()

    def _get_delimiter(self):
        d = self.cb_delimiter.get()
        if d == "\\t":
            return "\t"
        return d

    def _get_encoding(self):
        e = self.cb_encoding.get()
        if e == "自动检测":
            return None
        return e or None

    def _parse_and_preview(self):
        """解析文件并刷新预览"""
        if not self._file_path:
            return

        ext = os.path.splitext(self._file_path)[1].lower()
        has_header = self.has_header_var.get()

        try:
            if ext in ('.xlsx', '.xls'):
                columns, rows_display, rows_raw = Importer.parse_excel(
                    self._file_path, has_header=has_header)
            else:
                delimiter = self._get_delimiter()
                encoding = self._get_encoding()
                columns, rows_display, rows_raw = Importer.parse_csv(
                    self._file_path, delimiter=delimiter, has_header=has_header,
                    encoding=encoding)
        except Exception as e:
            messagebox.showerror("解析错误", f"无法解析文件:\n{e}")
            self._clear_preview()
            return

        self._parsed_columns = columns
        self._parsed_rows_display = rows_display[:20]  # 预览前 20 行
        self._parsed_rows_raw = rows_raw

        # 刷新 Treeview
        self.tree_preview.delete(*self.tree_preview.get_children())
        self.tree_preview['columns'] = columns
        for col in columns:
            self.tree_preview.heading(col, text=col)
            # 自适应宽度
            width = max(80, min(200, len(col) * 12 + 20))
            self.tree_preview.column(col, width=width, minwidth=60)

        for row in self._parsed_rows_display:
            self.tree_preview.insert("", "end", values=row)

        self.lbl_preview_info.config(text=f"共 {len(rows_raw)} 行，{len(columns)} 列")
        self.btn_start.config(state="normal" if columns and rows_raw else "disabled")

    def _clear_preview(self):
        self.tree_preview.delete(*self.tree_preview.get_children())
        self.tree_preview['columns'] = []
        self._parsed_columns = []
        self._parsed_rows_display = []
        self._parsed_rows_raw = []
        self.lbl_preview_info.config(text="共 0 行，0 列")
        self.btn_start.config(state="disabled")

    def _on_options_changed(self):
        self._parse_and_preview()

    def _on_conn_selected(self, event):
        conn_name = self.cb_conn.get()
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        if not conn_data:
            return

        # 隐藏 Schema 行（默认）
        self.lbl_schema.grid_forget()
        self.cb_schema.grid_forget()

        progress = ProgressDialog(self, message="正在连接并获取数据库列表...")
        def fetch():
            try:
                dbs = self.db_ops.get_databases(conn_data)
                self.after(0, lambda: self._on_dbs_fetched(dbs, progress, conn_data))
            except Exception as e:
                self.after(0, lambda: self._on_fetch_error(str(e), progress))
        threading.Thread(target=fetch, daemon=True).start()

    def _on_dbs_fetched(self, dbs, progress, conn_data):
        progress.close()
        self.cb_db['values'] = dbs
        if dbs:
            self.cb_db.set(dbs[0])
            self._on_db_selected(None)

    def _on_db_selected(self, event):
        conn_name = self.cb_conn.get()
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        if not conn_data or conn_data.get('db_type') != 'PostgreSQL':
            self._load_tables()
            return

        selected_db = self.cb_db.get()
        if not selected_db:
            return

        # 显示 Schema 选择
        self.lbl_schema.grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.cb_schema.grid(row=0, column=3, sticky="ew", padx=(0, 8))

        def fetch():
            try:
                schemas = self.db_ops.get_schemas(conn_data, database=selected_db)
                def update():
                    self.cb_schema['values'] = schemas
                    if 'public' in schemas:
                        self.cb_schema.set('public')
                    elif schemas:
                        self.cb_schema.set(schemas[0])
                    self._load_tables()
                self.after(0, update)
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    def _load_tables(self):
        conn_name = self.cb_conn.get()
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        if not conn_data:
            return
        selected_db = self.cb_db.get()
        if not selected_db:
            return
        schema = self.cb_schema.get() if self.lbl_schema.winfo_ismapped() else None

        def fetch():
            try:
                tables = self.db_ops.get_tables(conn_data, database=selected_db, schema=schema)
                # 获取所有表名
                table_names = [t['name'] if isinstance(t, dict) else (t[0] if isinstance(t, tuple) else t) for t in tables]
                self.after(0, lambda: self._on_tables_fetched(table_names))
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    def _on_tables_fetched(self, table_names):
        self.cb_table['values'] = table_names

    def _on_fetch_error(self, err_msg, progress):
        progress.close()
        messagebox.showerror("获取数据库列表失败", err_msg)

    def _start_import(self):
        conn_name = self.cb_conn.get()
        selected_db = self.cb_db.get()
        selected_schema = self.cb_schema.get() if self.lbl_schema.winfo_ismapped() else None
        table_name = self.cb_table.get().strip()

        if not conn_name or not selected_db or not table_name:
            messagebox.showwarning("提示", "请选择连接、数据库和目标表名")
            return

        if not self._parsed_columns or not self._parsed_rows_raw:
            messagebox.showwarning("提示", "请先选择并解析数据文件")
            return

        conn_data = next(c for c in self.all_connections if c['name'] == conn_name)
        mode = self.import_mode.get()
        total_rows = len(self._parsed_rows_raw)

        # 确认
        mode_labels = {'append': '追加 (INSERT)', 'replace': '清空并导入 (REPLACE)', 'create': '新建表 (CREATE)'}
        msg = (f"即将向 [{selected_db}] 中的表 [{table_name}] 导入 {total_rows} 行数据。\n"
               f"模式: {mode_labels.get(mode, mode)}\n\n确认开始？")
        if not messagebox.askyesno("确认导入", msg):
            return

        progress = ProgressDialog(self, title="导入中", message="正在导入数据...")

        cancel_event = threading.Event()

        def run():
            try:
                success, result = Importer.import_to_table(
                    self.db_ops, conn_data, table_name,
                    self._parsed_columns, self._parsed_rows_raw,
                    mode=mode, database=selected_db, schema=selected_schema,
                    cancel_event=cancel_event,
                    progress_callback=lambda pct, msg: self.after(0, lambda: progress.update_progress(pct, msg))
                )
                self.after(0, lambda: self._on_import_done(progress, success, result, total_rows))
            except Exception as e:
                self.after(0, lambda: self._on_import_done(progress, False, str(e), total_rows))

        threading.Thread(target=run, daemon=True).start()

    def _on_import_done(self, progress, success, result, total_rows):
        progress.close()
        if success:
            messagebox.showinfo("导入完成",
                                f"成功导入 {result} / {total_rows} 行数据到目标表。")
            self.destroy()
        else:
            messagebox.showerror("导入失败",
                                 f"导入过程中发生错误:\n{result}")
