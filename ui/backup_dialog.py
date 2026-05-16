"""数据库备份恢复对话框"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from models.db_storage import DBStorage
from core.backup_manager import BackupManager
from core.ui_style import apply_navicat_style


class BackupDialog(tk.Toplevel):
    """备份/恢复对话框，支持 MySQL (mysqldump) 和 PostgreSQL (pg_dump)"""

    def __init__(self, parent):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title("数据库备份与恢复")
        self.resizable(True, True)
        self._width = 750
        self._height = 880
        self.minsize(680, 750)

        x = (self.winfo_screenwidth() - self._width) // 2
        y = (self.winfo_screenheight() - self._height) // 2
        self.geometry(f"{self._width}x{self._height}+{x}+{y}")

        self.storage = DBStorage()
        self.backup_mgr = BackupManager()
        self.all_connections = self.storage.get_all_connections()

        self._running = False      # 防止重复点击
        self._cancel_event = threading.Event()

        self._init_ui()
        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        """创建 UI 布局 - Navicat 风格"""

        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # ── 连接选择（两模式共用） ──────────────────────────
        conn_frame = ttk.LabelFrame(main_frame, text="连接", padding=(12, 8))
        conn_frame.pack(fill="x", pady=(0, 12))

        # 使用 grid 布局，左侧标签固定宽度，右侧自适应
        ttk.Label(conn_frame, text="连接:", width=8).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.conn_combo = ttk.Combobox(conn_frame, state="readonly", width=45)
        self.conn_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        conn_frame.columnconfigure(1, weight=1)

        # 填充连接列表
        self.conn_map = {}  # {display_name: conn_data}
        for c in self.all_connections:
            label = f"{c.get('name')} ({c.get('db_type', 'MySQL')})"
            self.conn_map[label] = c
        self.conn_combo["values"] = list(self.conn_map.keys())
        if self.conn_combo["values"]:
            self.conn_combo.current(0)
        self.conn_combo.bind("<<ComboboxSelected>>", self._on_conn_change)

        self.conn_status_label = ttk.Label(conn_frame, text="", foreground="#666666", font=("Microsoft YaHei", 8))
        self.conn_status_label.grid(row=1, column=1, sticky="w", pady=(4, 0))

        # ── 选项卡：备份 / 恢复 ──────────────────────────────
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 12))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # --- 备份页 ---
        self.backup_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.backup_frame, text="  备份  ")

        # 数据库/Schema 选择 - 紧凑行
        db_frame = ttk.Frame(self.backup_frame)
        db_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(db_frame, text="数据库:", width=8).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.bk_db_combo = ttk.Combobox(db_frame, state="readonly", width=35)
        self.bk_db_combo.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.bk_load_db_btn = ttk.Button(db_frame, text="⟳ 刷新", command=self._load_databases_backup, width=8)
        self.bk_load_db_btn.grid(row=0, column=2, padx=(0, 0))

        # 选项 - 使用简洁的复选框布局
        opt_frame = ttk.LabelFrame(self.backup_frame, text="备份选项", padding=(12, 8))
        opt_frame.pack(fill="x", pady=(0, 10))

        self.bk_include_data = tk.BooleanVar(value=True)
        self.bk_include_structure = tk.BooleanVar(value=True)
        cb_frame = ttk.Frame(opt_frame)
        cb_frame.pack(anchor="w")
        ttk.Checkbutton(cb_frame, text="包含数据 (INSERT语句)", variable=self.bk_include_data).pack(side="left", padx=(0, 20))
        ttk.Checkbutton(cb_frame, text="包含表结构 (CREATE TABLE)", variable=self.bk_include_structure).pack(side="left", padx=(0, 0))

        # 表选择 - 更大的列表区域
        table_frame = ttk.LabelFrame(self.backup_frame, text="选择表 (留空 = 全部表)", padding=(12, 8))
        table_frame.pack(fill="both", expand=True, pady=(0, 10))

        list_frame = ttk.Frame(table_frame)
        list_frame.pack(fill="both", expand=True)

        self.bk_table_list = tk.Listbox(list_frame, selectmode="multiple",
                                         height=8, font=("Microsoft YaHei", 9),
                                         borderwidth=1, relief="solid")
        vbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.bk_table_list.yview)
        self.bk_table_list.configure(yscrollcommand=vbar.set)
        self.bk_table_list.pack(side="left", fill="both", expand=True, padx=(0, 2))
        vbar.pack(side="right", fill="y")

        btn_frame = ttk.Frame(table_frame)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="◉ 全选", command=self._bk_select_all, width=10).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="○ 取消全选", command=self._bk_deselect_all, width=10).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="⟳ 刷新列表", command=self._load_tables_backup, width=10).pack(side="right")

        # 输出路径
        out_frame = ttk.Frame(self.backup_frame)
        out_frame.pack(fill="x", pady=(0, 0))
        ttk.Label(out_frame, text="输出路径:", width=8).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.bk_path_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.bk_path_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(out_frame, text="浏览...", command=self._bk_browse_output, width=8).grid(row=0, column=2)
        out_frame.columnconfigure(1, weight=1)

        # --- 恢复页 ---
        self.restore_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.restore_frame, text="  恢复  ")

        # 数据库选择 - 紧凑行
        r_db_frame = ttk.Frame(self.restore_frame)
        r_db_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(r_db_frame, text="目标数据库:", width=10).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.rs_db_combo = ttk.Combobox(r_db_frame, state="readonly", width=35)
        self.rs_db_combo.grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Button(r_db_frame, text="⟳ 刷新", command=self._load_databases_restore, width=8).grid(row=0, column=2)

        # 备份文件选择
        file_frame = ttk.Frame(self.restore_frame)
        file_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(file_frame, text="备份文件:", width=10).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.rs_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.rs_file_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(file_frame, text="浏览...", command=self._rs_browse_file, width=8).grid(row=0, column=2)
        file_frame.columnconfigure(1, weight=1)

        # 提示 - 使用更醒目的样式
        rs_hint = ttk.Label(self.restore_frame,
                            text="⚠ 注意: 恢复操作将覆盖目标数据库数据，请谨慎操作！",
                            foreground="#D9534F", font=("Microsoft YaHei", 9))
        rs_hint.pack(fill="x", pady=(0, 0))

        # ── 操作按钮区域 ──────────────────────────
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=(0, 8))

        # 左侧操作按钮
        btn_left = ttk.Frame(action_frame)
        btn_left.pack(side="left")
        self.bk_start_btn = ttk.Button(btn_left, text="▶ 开始备份", command=self._start_backup, width=12, style="Navicat.Primary.TButton")
        self.rs_start_btn = ttk.Button(btn_left, text="▶ 开始恢复", command=self._start_restore, width=12, style="Navicat.Primary.TButton")
        # 默认显示备份按钮
        self.bk_start_btn.pack(side="left", padx=(0, 6))

        # 右侧取消按钮
        self.cancel_btn = ttk.Button(action_frame, text="✖ 取消",
                                      command=self._cancel_operation, state="disabled", width=10)
        self.cancel_btn.pack(side="right")

        # ── 进度条 ────────────────────────────────────────────
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill="x", pady=(0, 8))
        self._progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, orient="horizontal",
            mode="determinate", variable=self._progress_var
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_label = ttk.Label(self.progress_frame, text="0%", width=5, font=("Consolas", 9))
        self.progress_label.pack(side="left")
        # 初始隐藏
        self.progress_frame.pack_forget()

        # ── 日志输出 ──────────────────────────────────────────
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding=(10, 6))
        log_frame.pack(fill="x")

        self.log_text = tk.Text(log_frame, height=5, font=("Consolas", 9),
                                 wrap="word", state="disabled",
                                 relief="solid", borderwidth=1)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(0, 2))
        scrollbar.pack(side="right", fill="y")

        # 初始加载
        self._on_conn_change()
        self._update_tool_status()

    def _on_conn_change(self, event=None):
        """连接选择变更时刷新状态"""
        conn = self._get_selected_conn()
        if conn:
            self.conn_status_label.config(
                text=f"{conn.get('db_type', 'MySQL')} @ {conn.get('host')}:{conn.get('port')}"
            )
            self._load_databases_backup()
            self._load_databases_restore()
            self._load_tables_backup()

    def _on_tab_changed(self, event=None):
        """选项卡切换时动态显示对应的操作按钮"""
        if self._running or not hasattr(self, 'bk_start_btn'):
            return
        tab = self.notebook.index(self.notebook.select())
        if tab == 0:  # 备份页
            self.bk_start_btn.pack(side="left", padx=(0, 6))
            self.rs_start_btn.pack_forget()
        else:  # 恢复页
            self.rs_start_btn.pack(side="left", padx=(0, 6))
            self.bk_start_btn.pack_forget()

    def _get_selected_conn(self):
        """获取当前选中的连接配置"""
        name = self.conn_combo.get()
        return self.conn_map.get(name)

    def _load_databases_backup(self):
        """加载备份页的数据库列表"""
        conn = self._get_selected_conn()
        if not conn:
            return

        self.bk_db_combo.set("")
        self.bk_db_combo["values"] = []
        self.bk_load_db_btn.config(state="disabled")

        def _load():
            from core.db_operations import DBOperations
            try:
                db_ops = DBOperations()
                dbs = db_ops.get_databases(conn)
                self.after(0, lambda: self._populate_db_combo_backup(dbs, conn.get("database", "")))
            except Exception as e:
                self.after(0, lambda: self._populate_db_combo_backup([], "", str(e)))
            finally:
                self.after(0, lambda: self.bk_load_db_btn.config(state="normal"))

        threading.Thread(target=_load, daemon=True).start()

    def _populate_db_combo_backup(self, databases, default_db, error=None):
        if error:
            self._log(f"加载数据库列表失败: {error}")
            return
        self.bk_db_combo["values"] = databases
        if default_db in databases:
            self.bk_db_combo.set(default_db)
        elif databases:
            self.bk_db_combo.current(0)
        # 库列表加载完成后自动加载表列表
        self._load_tables_backup()

    def _load_databases_restore(self):
        """加载恢复页的数据库列表"""
        conn = self._get_selected_conn()
        if not conn:
            return

        self.rs_db_combo.set("")
        self.rs_db_combo["values"] = []

        def _load():
            from core.db_operations import DBOperations
            try:
                db_ops = DBOperations()
                dbs = db_ops.get_databases(conn)
                self.after(0, lambda: self._populate_db_combo_restore(dbs, conn.get("database", "")))
            except Exception as e:
                self.after(0, lambda: self._log(f"加载数据库列表失败: {e}"))

        threading.Thread(target=_load, daemon=True).start()

    def _populate_db_combo_restore(self, databases, default_db):
        self.rs_db_combo["values"] = databases
        if default_db in databases:
            self.rs_db_combo.set(default_db)
        elif databases:
            self.rs_db_combo.current(0)

    def _load_tables_backup(self):
        """加载表列表到 Listbox"""
        conn = self._get_selected_conn()
        db_name = self.bk_db_combo.get()
        if not conn or not db_name:
            return

        self.bk_table_list.delete(0, tk.END)

        def _load():
            from core.db_operations import DBOperations
            try:
                db_ops = DBOperations()
                tables = db_ops.get_tables(conn, db_name)
                self.after(0, lambda: self._populate_table_list(tables))
            except Exception as e:
                self.after(0, lambda: self._log(f"加载表列表失败: {e}"))

        threading.Thread(target=_load, daemon=True).start()

    def _populate_table_list(self, tables):
        self.bk_table_list.delete(0, tk.END)
        for t in tables:
            if isinstance(t, dict):
                name = t.get('name', '')
                comment = t.get('comment', '')
                display = f"{name} -- {comment}" if comment else name
            else:
                display = str(t)
            self.bk_table_list.insert(tk.END, display)

    def _bk_select_all(self):
        self.bk_table_list.select_set(0, tk.END)

    def _bk_deselect_all(self):
        self.bk_table_list.selection_clear(0, tk.END)

    def _bk_browse_output(self):
        """选择备份输出路径"""
        conn = self._get_selected_conn()
        db_type = conn.get("db_type", "MySQL") if conn else "MySQL"
        ext = ".sql"
        default_name = f"backup_{self.bk_db_combo.get() or 'unknown'}_{_timestamp()}{ext}"
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("SQL 文件", "*.sql"), ("所有文件", "*.*")],
            initialfile=default_name,
            title="选择备份文件保存路径"
        )
        if path:
            self.bk_path_var.set(path)

    def _rs_browse_file(self):
        """选择恢复的备份文件"""
        path = filedialog.askopenfilename(
            filetypes=[("SQL 文件", "*.sql"), ("所有文件", "*.*")],
            title="选择备份文件"
        )
        if path:
            self.rs_file_var.set(path)

    def _update_tool_status(self):
        """检查命令行工具是否可用（纯 Python 模式下不需要）"""
        conn = self._get_selected_conn()
        if not conn:
            return
        db_type = conn.get("db_type", "MySQL")
        tools = BackupManager.get_available_tools(db_type)
        all_available = all(info["available"] for info in tools.values())
        if all_available:
            self._log("工具检测: ✅ CLI 工具可用 (已使用内置 Python 引擎，无需外部工具)")
        else:
            missing = [t for t, info in tools.items() if not info["available"]]
            self._log(f"工具检测: 未找到 {', '.join(missing)} (内置 Python 引擎运行，无需外部工具)")

    # ── 备份执行 ──────────────────────────────────────────────

    def _start_backup(self):
        if self._running:
            return

        conn = self._get_selected_conn()
        db_name = self.bk_db_combo.get()
        output_path = self.bk_path_var.get().strip()

        if not conn:
            messagebox.showwarning("提示", "请选择数据库连接")
            return
        if not db_name:
            messagebox.showwarning("提示", "请选择数据库")
            return
        if not output_path:
            messagebox.showwarning("提示", "请选择输出路径")
            return
        if not self.bk_include_data.get() and not self.bk_include_structure.get():
            messagebox.showwarning("提示", "至少需要选择备份结构或数据")
            return

        # 获取选择的表
        sel_indices = self.bk_table_list.curselection()
        tables = [self.bk_table_list.get(i) for i in sel_indices] if sel_indices else None

        # 确认对话框
        table_count = len(tables) if tables else 0
        tables_summary = f" ({table_count} 张表)" if table_count else " (全部表)"
        if not messagebox.askyesno("确认备份",
            f"确认备份数据库「{db_name}」吗？\n\n"
            f"连接: {conn.get('name')}\n"
            f"数据库: {db_name}{tables_summary}\n"
            f"包含数据: {'是' if self.bk_include_data.get() else '否'}\n"
            f"包含结构: {'是' if self.bk_include_structure.get() else '否'}\n"
            f"输出文件: {output_path}\n\n"
            "此操作可能耗时较长，请确保网络稳定。"):
            return

        # 复制连接配置并替换数据库名
        import copy
        conn_copy = copy.deepcopy(conn)
        conn_copy["database"] = db_name

        self._set_running(True, is_backup=True)

        def _run():
            def log_cb(msg, progress=None):
                self.after(0, lambda: self._log(msg))
                if progress is not None:
                    self._progress_var.set(progress)
                    self.progress_label.config(text=f"  {progress}%")

            success, message = self.backup_mgr.backup_database(
                conn_copy, output_path,
                tables=tables,
                include_data=self.bk_include_data.get(),
                include_structure=self.bk_include_structure.get(),
                progress_callback=log_cb,
                cancel_event=self._cancel_event
            )

            self.after(0, lambda: self._on_backup_done(success, message))

        threading.Thread(target=_run, daemon=True).start()

    def _on_backup_done(self, success, message):
        self._set_running(False)
        self._log(message)
        if success:
            messagebox.showinfo("备份完成", message)
        else:
            messagebox.showerror("备份失败", message)

    # ── 恢复执行 ──────────────────────────────────────────────

    def _start_restore(self):
        if self._running:
            return

        conn = self._get_selected_conn()
        db_name = self.rs_db_combo.get()
        input_path = self.rs_file_var.get().strip()

        if not conn:
            messagebox.showwarning("提示", "请选择数据库连接")
            return
        if not db_name:
            messagebox.showwarning("提示", "请选择目标数据库")
            return
        if not input_path:
            messagebox.showwarning("提示", "请选择备份文件")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("错误", "备份文件不存在")
            return

        # 确认对话框
        if not messagebox.askyesno("确认恢复",
            f"确认将数据恢复到数据库「{db_name}」吗？\n\n"
            f"连接: {conn.get('name')}\n"
            f"文件: {os.path.basename(input_path)}\n\n"
            "此操作将写入目标数据库，请确保已做好必要备份。"):
            return

        import copy
        conn_copy = copy.deepcopy(conn)
        conn_copy["database"] = db_name

        self._set_running(True, is_backup=False)

        def _run():
            def log_cb(msg, progress=None):
                self.after(0, lambda: self._log(msg))
                if progress is not None:
                    self._progress_var.set(progress)
                    self.progress_label.config(text=f"  {progress}%")

            success, message = self.backup_mgr.restore_database(
                conn_copy, input_path,
                progress_callback=log_cb,
                cancel_event=self._cancel_event
            )

            self.after(0, lambda: self._on_restore_done(success, message))

        threading.Thread(target=_run, daemon=True).start()

    def _on_restore_done(self, success, message):
        self._set_running(False)
        self._log(message)
        if success:
            messagebox.showinfo("恢复完成", message)
        else:
            messagebox.showerror("恢复失败", message)

    # ── 通用控制 ──────────────────────────────────────────────

    def _set_running(self, running, is_backup=True):
        self._running = running
        state = "disabled" if running else "normal"

        # 禁用连接切换
        self.conn_combo.config(state="readonly" if not running else "disabled")

        # 按钮状态（只禁用在运行的按钮，取消按钮反着来）
        if is_backup:
            self.bk_start_btn.config(state=state)
            self.rs_start_btn.config(state="disabled" if running else "normal")
        else:
            self.rs_start_btn.config(state=state)
            self.bk_start_btn.config(state="disabled" if running else "normal")
        self.cancel_btn.config(state="normal" if running else "disabled")

        # 进度条控制
        if running:
            self._cancel_event.clear()
            self._progress_var.set(0)
            self.progress_label.config(text="  0%")
            # 在日志框之前重新显示进度条（保持原始位置）
            self.progress_frame.pack(before=self.log_text.master, fill="x", pady=(2, 4))
        else:
            self._cancel_event = threading.Event()

    def _cancel_operation(self):
        self._cancel_event.set()
        self._log("正在取消操作...")
        self.cancel_btn.config(state="disabled")

    def _log(self, message):
        """在日志框输出"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")


def _timestamp():
    """返回紧凑时间戳"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")
