import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime
from models.db_storage import DBStorage
from models.sync_history import SyncHistoryManager
from core.db_operations import DBOperations
from core.syncer import DatabaseSyncer
from core.ui_style import NavicatStyle, apply_navicat_style, center_window
from ui.sync_progress_dialog import SyncProgressDialog
from ui.progress_dialog import ProgressDialog

class SyncDialog(tk.Toplevel):
    def __init__(self, parent, source_conn_id=None, source_db=None, selected_tables=None, sync_mode="all"):
        super().__init__(parent)
        self.title("数据库同步向导")
        self.resizable(True, True)
        self.minsize(900, 550)

        # Navicat 风格：居中显示
        width, height = 1100, 700
        center_window(self, width, height)

        # 获取父窗口的主题设置，应用主题感知的 Navicat 风格
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)

        self.storage = DBStorage()
        self.db_ops = DBOperations()
        self.all_connections = self.storage.get_all_connections()

        self.init_source_conn_id = source_conn_id
        self.init_source_db = source_db
        self.init_selected_tables = selected_tables or []
        self.sync_mode = sync_mode # "all", "structure", "data"

        self._init_ui()
        self._apply_initial_values()

        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        # 底部按钮区 - Navicat 风格
        btn_container = ttk.Frame(self, padding=(20, 12))
        btn_container.pack(side="bottom", fill="x")

        ttk.Button(btn_container, text="取消", command=self.destroy, width=12).pack(side="right", padx=(8, 0))
        ttk.Button(btn_container, text="开始同步", command=self._start_sync, width=12, style="Navicat.Primary.TButton").pack(side="right")

        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(side="top", fill="both", expand=True)

        # 1. 源数据库配置 - Navicat 风格
        source_frame = ttk.LabelFrame(main_frame, text="源数据库", padding=(12, 8))
        source_frame.pack(fill="x", pady=(0, 12))
        source_frame.columnconfigure(1, weight=1)
        source_frame.columnconfigure(3, weight=1)

        ttk.Label(source_frame, text="连接:", width=NavicatStyle.LABEL_WIDTH, anchor="e").grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.cb_source_conn = ttk.Combobox(source_frame, values=[c['name'] for c in self.all_connections], state="readonly", width=NavicatStyle.COMBOBOX_WIDTH)
        self.cb_source_conn.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=6)
        self.cb_source_conn.bind("<<ComboboxSelected>>", lambda e: self._on_conn_selected("source"))

        ttk.Label(source_frame, text="数据库:", width=NavicatStyle.LABEL_WIDTH, anchor="e").grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=6)
        self.cb_source_db = ttk.Combobox(source_frame, values=[], state="readonly", width=NavicatStyle.COMBOBOX_WIDTH)
        self.cb_source_db.grid(row=0, column=3, sticky="ew", padx=(0, 0), pady=6)
        self.cb_source_db.bind("<<ComboboxSelected>>", lambda e: self._load_tables())

        # 2. 目标数据库配置 - Navicat 风格
        target_frame = ttk.LabelFrame(main_frame, text="目标数据库", padding=(12, 8))
        target_frame.pack(fill="x", pady=(0, 12))
        target_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(3, weight=1)

        ttk.Label(target_frame, text="连接:", width=NavicatStyle.LABEL_WIDTH, anchor="e").grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.cb_target_conn = ttk.Combobox(target_frame, values=[c['name'] for c in self.all_connections], state="readonly", width=NavicatStyle.COMBOBOX_WIDTH)
        self.cb_target_conn.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=6)
        self.cb_target_conn.bind("<<ComboboxSelected>>", lambda e: self._on_conn_selected("target"))

        ttk.Label(target_frame, text="数据库:", width=NavicatStyle.LABEL_WIDTH, anchor="e").grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=6)
        self.cb_target_db = ttk.Combobox(target_frame, values=[], state="readonly", width=NavicatStyle.COMBOBOX_WIDTH)
        self.cb_target_db.grid(row=0, column=3, sticky="ew", padx=(0, 0), pady=6)

        # 3. 表选择 (限制 Treeview 的高度，防止挤占空间)
        table_frame = ttk.LabelFrame(main_frame, text="选择同步表", padding=10)
        table_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # 搜索与全选 - Navicat 风格
        tool_frame = ttk.Frame(table_frame)
        tool_frame.pack(fill="x", pady=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self._filter_tables())
        ttk.Label(tool_frame, text="搜索:").pack(side="left", padx=(0, 6))
        ttk.Entry(tool_frame, textvariable=self.search_var, width=25).pack(side="left", padx=(0, 10))

        ttk.Button(tool_frame, text="◉ 全选", command=self._select_all, width=8).pack(side="right", padx=(4, 0))
        ttk.Button(tool_frame, text="○ 全不选", command=self._deselect_all, width=8).pack(side="right", padx=(4, 0))
        ttk.Button(tool_frame, text="⟲ 刷新", command=self._load_tables, width=8).pack(side="right")

        # Treeview - Navicat 风格
        list_container = ttk.Frame(table_frame)
        list_container.pack(fill="both", expand=True)

        self.table_tree = ttk.Treeview(list_container, columns=("selected", "name"), show="headings", selectmode="none", height=12)
        self.table_tree.heading("selected", text="选择")
        self.table_tree.heading("name", text="表名")
        self.table_tree.column("selected", width=60, anchor="center")
        self.table_tree.column("name", width=850)

        self.table_tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.table_tree.yview)
        self.table_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # 绑定点击事件模拟复选框
        self.table_tree.bind("<Button-1>", self._on_tree_click)

        self.all_tables = []

        # 4. 同步选项 - Navicat 风格
        option_frame = ttk.LabelFrame(main_frame, text="同步选项", padding=(12, 8))
        option_frame.pack(fill="x", pady=(12, 0))

        self.sync_structure = tk.BooleanVar(value=True)
        self.cb_sync_struct = ttk.Checkbutton(option_frame, text="同步表结构", variable=self.sync_structure)
        self.cb_sync_struct.grid(row=0, column=0, padx=(0, 25))

        self.sync_data = tk.BooleanVar(value=True)
        self.cb_sync_data = ttk.Checkbutton(option_frame, text="同步表数据", variable=self.sync_data)
        self.cb_sync_data.grid(row=0, column=1, padx=(0, 25))

        # 根据 sync_mode 调整
        if self.sync_mode == "structure":
            self.sync_data.set(False)
            self.cb_sync_data.configure(state="disabled")
            self.title("表结构同步向导")
        elif self.sync_mode == "data":
            self.sync_structure.set(False)
            self.cb_sync_struct.configure(state="disabled")
            self.title("数据同步向导")

        ttk.Label(option_frame, text="冲突策略:", width=10, anchor="e").grid(row=0, column=2, sticky="ew", padx=(10, 5))
        self.conflict_strategy = ttk.Combobox(option_frame, values=["overwrite", "skip"], state="readonly", width=12)
        self.conflict_strategy.set("overwrite")
        self.conflict_strategy.grid(row=0, column=3, sticky="w")

    def _apply_initial_values(self):
        """应用初始传入的预选值"""
        if self.init_source_conn_id:
            conn = next((c for c in self.all_connections if c['id'] == self.init_source_conn_id), None)
            if conn:
                self.cb_source_conn.set(conn['name'])
                
                # 预选库名
                if self.init_source_db:
                    self.cb_source_db.set(self.init_source_db)
                    
                    # 加载表列表
                    progress = ProgressDialog(self, message=f"正在拉取表列表...")
                    def fetch_and_select():
                        try:
                            table_names = self.db_ops.get_tables(conn, database=self.init_source_db)
                            tables = []
                            for t in table_names:
                                name = t['name'] if isinstance(t, dict) else t
                                selected = name in self.init_selected_tables
                                tables.append({'name': name, 'selected': selected})
                            
                            self.after(0, lambda: self._on_tables_fetched(tables, progress))
                        except Exception as e:
                            self.after(0, lambda: self._on_fetch_error(str(e), progress))
                    
                    threading.Thread(target=fetch_and_select, daemon=True).start()
                else:
                    # 仅加载数据库列表
                    self._on_conn_selected("source")

    def _on_conn_selected(self, side):
        conn_name = self.cb_source_conn.get() if side == "source" else self.cb_target_conn.get()
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        if not conn_data: return
        
        progress = ProgressDialog(self, message=f"正在连接{side}服务器并拉取库列表...")
        
        def fetch_dbs():
            try:
                dbs = self.db_ops.get_databases(conn_data)
                self.after(0, lambda: self._on_dbs_fetched(side, dbs, progress))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._on_fetch_error(err_msg, progress))

        threading.Thread(target=fetch_dbs, daemon=True).start()

    def _on_dbs_fetched(self, side, dbs, progress):
        progress.close()
        if side == "source":
            self.cb_source_db['values'] = dbs
            if dbs: 
                self.cb_source_db.set(dbs[0])
                self._load_tables()
        else:
            self.cb_target_db['values'] = dbs
            if dbs: self.cb_target_db.set(dbs[0])

    def _on_fetch_error(self, err_msg, progress):
        progress.close()
        messagebox.showerror("连接失败", f"无法拉取元数据: {err_msg}")

    def _load_tables(self):
        conn_name = self.cb_source_conn.get()
        db_name = self.cb_source_db.get()
        if not conn_name or not db_name: return
        
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        progress = ProgressDialog(self, message=f"正在从库 [{db_name}] 拉取表列表...")

        def fetch_tables():
            try:
                # get_tables 返回字典列表 {'name': str, 'comment': str}，只需添加 selected 字段
                tables = self.db_ops.get_tables(conn_data, database=db_name)
                for t in tables:
                    t['selected'] = False
                self.after(0, lambda: self._on_tables_fetched(tables, progress))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._on_fetch_error(err_msg, progress))

        threading.Thread(target=fetch_tables, daemon=True).start()

    def _on_tables_fetched(self, tables, progress):
        progress.close()
        self.all_tables = tables
        self._filter_tables()

    def _filter_tables(self):
        search_term = self.search_var.get().lower()
        for item in self.table_tree.get_children():
            self.table_tree.delete(item)
            
        for t in self.all_tables:
            if search_term in t['name'].lower():
                mark = "[X]" if t['selected'] else "[ ]"
                self.table_tree.insert("", "end", values=(mark, t['name']))

    def _on_tree_click(self, event):
        item_id = self.table_tree.identify_row(event.y)
        if not item_id: return
        
        values = self.table_tree.item(item_id, "values")
        table_name = values[1]
        
        for t in self.all_tables:
            if t['name'] == table_name:
                t['selected'] = not t['selected']
                mark = "[X]" if t['selected'] else "[ ]"
                self.table_tree.item(item_id, values=(mark, table_name))
                break

    def _select_all(self):
        for t in self.all_tables: t['selected'] = True
        self._filter_tables()

    def _deselect_all(self):
        for t in self.all_tables: t['selected'] = False
        self._filter_tables()

    def _deselect_filtered(self):
        search_term = self.search_var.get().lower()
        for t in self.all_tables:
            if search_term in t['name'].lower():
                t['selected'] = False
        self._filter_tables()

    def _start_sync(self):
        # 1. 校验输入
        source_conn_name = self.cb_source_conn.get()
        target_conn_name = self.cb_target_conn.get()
        source_db = self.cb_source_db.get()
        target_db = self.cb_target_db.get()
        
        if not source_conn_name or not target_conn_name or not source_db or not target_db:
            messagebox.showwarning("提示", "请选择完整的源/目标连接和数据库")
            return
            
        selected_tables = [t['name'] for t in self.all_tables if t['selected']]
        if not selected_tables:
            messagebox.showwarning("提示", "请至少选择一张要同步的表")
            return
            
        source_conn = next(c for c in self.all_connections if c['name'] == source_conn_name).copy()
        target_conn = next(c for c in self.all_connections if c['name'] == target_conn_name).copy()
        
        # 强制更新库名
        source_conn['database'] = source_db
        target_conn['database'] = target_db
        
        # 检查类型是否一致
        if source_conn['db_type'] != target_conn['db_type']:
            messagebox.showerror("不支持", "目前仅支持同类型数据库之间的同步 (MySQL -> MySQL 或 PG -> PG)")
            return

        # 2. 准备同步任务
        options = {
            'tables': selected_tables,
            'sync_structure': self.sync_structure.get(),
            'sync_data': self.sync_data.get(),
            'conflict_strategy': self.conflict_strategy.get()
        }
        
        cancel_event = threading.Event()
        progress_dialog = SyncProgressDialog(self, cancel_event)
        
        # 3. 定义回调
        def progress_callback(event_type, data):
            progress_dialog.queue.put((event_type, data))
            if event_type == "done":
                # 保存历史记录
                history_record = {
                    'start_time': start_time_str,
                    'end_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'source_conn_id': source_conn['id'],
                    'source_db': source_db,
                    'target_conn_id': target_conn['id'],
                    'target_db': target_db,
                    'tables': selected_tables,
                    'sync_structure': options['sync_structure'],
                    'sync_data': options['sync_data'],
                    'status': data['status'],
                    'log_path': data.get('log_path'),
                    'error_summary': data.get('error')
                }
                SyncHistoryManager.save_record(history_record)

        # 4. 启动线程
        start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        syncer = DatabaseSyncer(source_conn, target_conn, options, progress_callback, cancel_event)
        threading.Thread(target=syncer.run, daemon=True).start()
