"""AI 会话初始化向导，选择连接→数据库→表，生成表结构上下文"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
from models.db_storage import DBStorage
from core.db_operations import DBOperations
from core.ai.context_builder import ContextBuilder
from ui.progress_dialog import ProgressDialog


class SessionWizard(tk.Toplevel):
    """初始化 AI 会话向导"""

    def __init__(self, parent, conn_data=None, db_name=None, schema_name=None, db_ops=None,
                 on_complete=None):
        """
        :param parent: 父窗口
        :param conn_data: 当前连接数据（预选）
        :param db_name: 当前数据库名（预选）
        :param schema_name: 当前 Schema 名（预选）
        :param db_ops: DBOperations 实例
        :param on_complete: 完成回调 on_complete(context_text, conn_id, database, schema, selected_tables)
        """
        super().__init__(parent)
        self.title("初始化 AI 会话")
        self.parent = parent
        self.on_complete = on_complete
        self.db_ops = db_ops or DBOperations()
        self.storage = DBStorage()

        self._all_connections = self.storage.get_all_connections()
        self._all_tables = []
        self._selected_conn_data = conn_data

        width, height = 520, 560
        self.resizable(True, True)
        self.minsize(440, 480)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self._init_ui()

        # 预选当前连接
        if conn_data:
            for i, c in enumerate(self._all_connections):
                if c['id'] == conn_data.get('id'):
                    self.conn_combo.current(i)
                    self._on_conn_selected()
                    break
            if db_name:
                self.db_var.set(db_name)
                self._on_db_selected()
            if schema_name:
                self.schema_var.set(schema_name or '')

        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        """构建界面"""
        # 用 grid 布局：上方内容区占满，下方按钮固定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        main_frame = ttk.Frame(self, padding=15)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.rowconfigure(2, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # 步骤 1: 选择连接
        step1_frame = ttk.LabelFrame(main_frame, text="步骤 1: 选择数据库连接", padding=8)
        step1_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.conn_var = tk.StringVar()
        self.conn_combo = ttk.Combobox(step1_frame, textvariable=self.conn_var,
                                        state="readonly", width=45)
        self.conn_combo.pack(fill="x")
        conn_names = [f"{c['name']} ({c.get('db_type', 'MySQL')})" for c in self._all_connections]
        self.conn_combo['values'] = conn_names
        self.conn_combo.bind("<<ComboboxSelected>>", lambda e: self._on_conn_selected())

        # 步骤 2: 选择数据库/模式
        step2_frame = ttk.LabelFrame(main_frame, text="步骤 2: 选择数据库", padding=8)
        step2_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        db_row = ttk.Frame(step2_frame)
        db_row.pack(fill="x")
        ttk.Label(db_row, text="数据库:").pack(side="left")
        self.db_var = tk.StringVar()
        self.db_combo = ttk.Combobox(db_row, textvariable=self.db_var,
                                      state="readonly", width=35)
        self.db_combo.pack(side="left", padx=5)
        self.db_combo.bind("<<ComboboxSelected>>", lambda e: self._on_db_selected())

        # Schema 选择（仅 PostgreSQL）
        self.schema_row = ttk.Frame(step2_frame)
        ttk.Label(self.schema_row, text="模式:").pack(side="left")
        self.schema_var = tk.StringVar()
        self.schema_combo = ttk.Combobox(self.schema_row, textvariable=self.schema_var,
                                          state="readonly", width=35)
        self.schema_combo.pack(side="left", padx=5)

        # 步骤 3: 选择表
        self.step3_frame = ttk.LabelFrame(main_frame, text="步骤 3: 选择要提供给 AI 的表", padding=8)
        self.step3_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))

        # 搜索框 — 放在 self.step3_frame 顶部，先 pack 确保可见
        search_row = ttk.Frame(self.step3_frame)
        search_row.pack(side="top", fill="x", pady=(0, 5))
        ttk.Label(search_row, text="🔍", font=("Microsoft YaHei", 9)).pack(side="left", padx=(0, 3))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())
        search_entry = tk.Entry(search_row, textvariable=self._search_var,
                                 font=("Microsoft YaHei", 9), relief="solid", bd=1)
        search_entry.pack(side="left", fill="x", expand=True)

        # 操作按钮行
        btn_row = ttk.Frame(self.step3_frame)
        btn_row.pack(side="top", fill="x", pady=(0, 5))
        ttk.Button(btn_row, text="全选", command=self._select_all).pack(side="left", padx=2)
        ttk.Button(btn_row, text="全不选", command=self._deselect_all).pack(side="left", padx=2)
        ttk.Button(btn_row, text="反选", command=self._invert_selection).pack(side="left", padx=2)
        ttk.Button(btn_row, text="刷新", command=self._refresh_tables).pack(side="left", padx=(10, 2))

        # 表列表 Treeview — 最后 pack，填充剩余空间
        tree_frame = ttk.Frame(self.step3_frame)
        tree_frame.pack(side="top", fill="both", expand=True)

        self.table_tree = ttk.Treeview(tree_frame, columns=('select', 'table'), show='headings', height=8)
        self.table_tree.heading('select', text='')
        self.table_tree.heading('table', text='表名')
        self.table_tree.column('select', width=40, anchor='center')
        self.table_tree.column('table', width=350)
        self.table_tree.pack(side="left", fill="both", expand=True)
        self.table_tree.bind('<Button-1>', self._on_table_click)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.table_tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.table_tree.configure(yscrollcommand=tree_scroll.set)

        # 底部按钮（窗口级别，始终可见）
        bottom_frame = ttk.Frame(self, padding=(15, 5, 15, 10))
        bottom_frame.grid(row=1, column=0, sticky="ew")

        self.table_count_label = ttk.Label(bottom_frame, text="已选 0 个表", font=("Microsoft YaHei", 9))
        self.table_count_label.pack(side="left", padx=5)

        ttk.Button(bottom_frame, text="确认", command=self._on_confirm,
                    style="BigAction.TButton").pack(side="right", padx=3)
        ttk.Button(bottom_frame, text="取消", command=self.destroy).pack(side="right", padx=3)

    def _on_conn_selected(self):
        """选择连接后加载数据库列表"""
        idx = self.conn_combo.current()
        if idx < 0 or idx >= len(self._all_connections):
            return

        self._selected_conn_data = self._all_connections[idx]
        conn_data = self._selected_conn_data

        # 判断是否显示 Schema
        if conn_data.get('db_type') == 'PostgreSQL':
            self.schema_row.pack(fill="x", pady=(5, 0))
        else:
            self.schema_row.pack_forget()

        # 后台加载数据库列表
        self.db_combo.configure(values=["加载中..."])
        self.db_var.set('')
        self.schema_combo.configure(values=[])
        self.schema_var.set('')

        def load_dbs():
            try:
                dbs = self.db_ops.get_databases(conn_data)
                self.after(0, lambda: self.db_combo.configure(values=dbs))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("错误", f"获取数据库列表失败: {e}", parent=self))

        threading.Thread(target=load_dbs, daemon=True).start()

    def _on_db_selected(self):
        """选择数据库后加载表列表"""
        if not self._selected_conn_data:
            return

        db_name = self.db_var.get()
        if not db_name:
            return

        conn_data = self._selected_conn_data
        is_pg = conn_data.get('db_type') == 'PostgreSQL'

        # PostgreSQL: 加载 Schema 列表
        if is_pg:
            def load_schemas():
                try:
                    schemas = self.db_ops.get_schemas(conn_data, database=db_name)
                    self.after(0, lambda: self._update_schema_list(schemas))
                except Exception:
                    pass
            threading.Thread(target=load_schemas, daemon=True).start()

        # 加载表列表
        schema = self.schema_var.get() if is_pg else None

        # 显示加载状态
        self.step3_frame.configure(text="步骤 3: 加载中...")
        self.table_tree.delete(*self.table_tree.get_children())

        def load_tables():
            try:
                tables = self.db_ops.get_tables(conn_data, database=db_name, schema=schema)
                self.after(0, lambda: self._update_table_list(tables))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("错误", f"获取表列表失败: {e}", parent=self))

        threading.Thread(target=load_tables, daemon=True).start()

    def _update_schema_list(self, schemas):
        """更新 Schema 下拉列表"""
        self.schema_combo.configure(values=schemas)
        if schemas:
            default_schema = 'public' if 'public' in schemas else schemas[0]
            self.schema_var.set(default_schema)
            # Schema 选择变更后刷新表列表
            self.schema_combo.bind("<<ComboboxSelected>>", lambda e: self._on_db_selected())
            self._on_db_selected()

    def _update_table_list(self, tables):
        """更新表列表"""
        self._all_tables = [{'name': t['name'] if isinstance(t, dict) else t, 'selected': True} for t in tables]
        total = len(tables)
        self.step3_frame.configure(text=f"步骤 3: 选择表 (共 {total} 个)")
        self._render_table_list()

    def _refresh_tables(self):
        """刷新表列表"""
        self._on_db_selected()

    def _on_search_changed(self):
        """搜索关键词变化时重新渲染列表"""
        self._render_table_list()

    def _render_table_list(self):
        """渲染表列表到 Treeview（根据搜索关键词过滤）"""
        self.table_tree.delete(*self.table_tree.get_children())
        keyword = self._search_var.get().strip().lower()
        # 保存当前过滤后的表名→_all_tables索引映射
        self._filtered_map = []
        for i, t in enumerate(self._all_tables):
            if keyword and keyword not in t['name'].lower():
                continue
            mark = "[X]" if t['selected'] else "[ ]"
            self.table_tree.insert('', 'end', values=(mark, t['name']))
            self._filtered_map.append(i)
        self._update_count()

    def _on_table_click(self, event):
        """点击表名切换选中状态"""
        item = self.table_tree.identify_row(event.y)
        if not item:
            return
        tree_idx = self.table_tree.index(item)
        if not hasattr(self, '_filtered_map') or tree_idx >= len(self._filtered_map):
            return
        real_idx = self._filtered_map[tree_idx]
        self._all_tables[real_idx]['selected'] = not self._all_tables[real_idx]['selected']
        mark = "[X]" if self._all_tables[real_idx]['selected'] else "[ ]"
        self.table_tree.item(item, values=(mark, self._all_tables[real_idx]['name']))
        self._update_count()

    def _update_count(self):
        """更新已选计数"""
        count = sum(1 for t in self._all_tables if t['selected'])
        total = len(self._all_tables)
        self.table_count_label.configure(text=f"已选 {count} / {total} 个表")

    def _get_filtered_indices(self):
        """获取当前搜索过滤后的表索引列表"""
        keyword = self._search_var.get().strip().lower()
        return [i for i, t in enumerate(self._all_tables)
                if not keyword or keyword in t['name'].lower()]

    def _select_all(self):
        """全选（仅当前过滤结果）"""
        for i in self._get_filtered_indices():
            self._all_tables[i]['selected'] = True
        self._render_table_list()

    def _deselect_all(self):
        """全不选（仅当前过滤结果）"""
        for i in self._get_filtered_indices():
            self._all_tables[i]['selected'] = False
        self._render_table_list()

    def _invert_selection(self):
        """反选（仅当前过滤结果）"""
        for i in self._get_filtered_indices():
            self._all_tables[i]['selected'] = not self._all_tables[i]['selected']
        self._render_table_list()

    def _on_confirm(self):
        """确认按钮"""
        if not self._selected_conn_data:
            messagebox.showwarning("提示", "请先选择数据库连接", parent=self)
            return

        db_name = self.db_var.get()
        if not db_name:
            messagebox.showwarning("提示", "请选择数据库", parent=self)
            return

        selected = [t['name'] for t in self._all_tables if t['selected']]
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个表", parent=self)
            return

        schema = self.schema_var.get() if self._selected_conn_data.get('db_type') == 'PostgreSQL' else None

        # 显示进度对话框
        self._progress_dlg = ProgressDialog(self, title="加载表结构",
                                              message=f"正在加载表结构 (0/{len(selected)})...")
        self._progress_queue = queue.Queue()

        def build():
            try:
                context = ContextBuilder.build_context(
                    self.db_ops, self._selected_conn_data,
                    database=db_name, schema=schema, table_names=selected,
                    progress_callback=self._on_build_progress
                )
                self._progress_queue.put(('done', context))
            except Exception as e:
                error = str(e)
                self._progress_queue.put(('error', error))

        threading.Thread(target=build, daemon=True).start()
        self._poll_progress(db_name, schema, selected)

    def _on_build_progress(self, current, total, table_name):
        """构建进度回调（工作线程中调用）"""
        self._progress_queue.put(('progress', (current, total, table_name)))

    def _poll_progress(self, db_name, schema, selected):
        """轮询构建进度，更新 ProgressDialog"""
        while True:
            try:
                event_type, data = self._progress_queue.get_nowait()
                if event_type == 'progress':
                    current, total, table_name = data
                    try:
                        self._progress_dlg.set_message(f"正在加载 ({current}/{total}): {table_name}")
                    except tk.TclError:
                        pass
                elif event_type == 'done':
                    self._on_context_ready(data, db_name, schema, selected)
                    return
                elif event_type == 'error':
                    self._on_context_error(data)
                    return
            except queue.Empty:
                break
        self.after(80, lambda: self._poll_progress(db_name, schema, selected))

    def _on_context_ready(self, context, db_name, schema, selected):
        """上下文构建完成"""
        try:
            self._progress_dlg.close()
        except Exception:
            pass
        on_complete = self.on_complete
        self.destroy()
        if on_complete:
            on_complete(context, self._selected_conn_data.get('id'), db_name, schema, selected)

    def _on_context_error(self, error):
        """上下文构建失败"""
        try:
            self._progress_dlg.close()
        except Exception:
            pass
        try:
            messagebox.showerror("错误", f"构建表结构上下文失败: {error}", parent=self)
        except tk.TclError:
            pass
