import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from models.db_storage import DBStorage
from core.db_operations import DBOperations
from core.exporter import Exporter
from ui.progress_dialog import ProgressDialog
from core.ui_style import apply_navicat_style

class ERExportDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title("导出 ER 关系图向导")
        self.resizable(True, True)

        # 基础高度（不含 Schema 行）
        self._base_width = 500
        self._base_height = 450
        self._schema_extra = 75  # Schema 行展开时额外高度

        # 居中
        x = (self.winfo_screenwidth() / 2) - (self._base_width / 2)
        y = (self.winfo_screenheight() / 2) - (self._base_height / 2)
        self.geometry(f'{self._base_width}x{self._base_height}+{int(x)}+{int(y)}')
        
        self.storage = DBStorage()
        self.db_ops = DBOperations()
        self.all_connections = self.storage.get_all_connections()
        
        self._init_ui()
        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        self.main_frame = ttk.Frame(self, padding=20)
        self.main_frame.pack(fill="both", expand=True)
        
        # 使用 Grid 布局
        self.main_frame.columnconfigure(0, weight=1)
        
        ttk.Label(self.main_frame, text="该向导将分析数据库表结构及外键关联关系并导出。", 
                  foreground="gray", wraplength=450).grid(row=0, column=0, sticky="w", pady=(0, 15))

        # 1. 选择连接
        ttk.Label(self.main_frame, text="第一步: 选择数据库连接", font=("Microsoft YaHei", 10, "bold")).grid(row=1, column=0, sticky="w", pady=(0, 5))
        self.cb_conn = ttk.Combobox(self.main_frame, values=[c['name'] for c in self.all_connections], state="readonly")
        self.cb_conn.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.cb_conn.bind("<<ComboboxSelected>>", self._on_conn_selected)
        
        # 2. 选择数据库
        ttk.Label(self.main_frame, text="第二步: 选择目标数据库", font=("Microsoft YaHei", 10, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 5))
        self.cb_db = ttk.Combobox(self.main_frame, values=[], state="readonly")
        self.cb_db.grid(row=4, column=0, sticky="ew", pady=(0, 15))
        self.cb_db.bind("<<ComboboxSelected>>", self._on_db_selected)
        
        # 2.1 选择模式 (仅 PG 可见)
        self.schema_container = ttk.Frame(self.main_frame)
        self.lbl_schema = ttk.Label(self.schema_container, text="第 2.5 步: 选择模式 (Schema)", font=("Microsoft YaHei", 10, "bold"))
        self.lbl_schema.pack(anchor="w", pady=(0, 5))
        self.cb_schema = ttk.Combobox(self.schema_container, values=[], state="readonly")
        self.cb_schema.pack(fill="x", pady=(0, 15))
        # 初始不 grid
        
        # 3. 选择导出格式
        ttk.Label(self.main_frame, text="第三步: 选择导出格式", font=("Microsoft YaHei", 10, "bold")).grid(row=6, column=0, sticky="w", pady=(0, 5))
        self.format_mapping = {
            "HTML 交互可视化": "html",
            "Excel 关联明细表": "excel",
            "Markdown 文档": "markdown",
            "PDF 报告": "pdf"
        }
        self.cb_format = ttk.Combobox(self.main_frame, values=list(self.format_mapping.keys()), state="readonly")
        self.cb_format.set("HTML 交互可视化")
        self.cb_format.grid(row=7, column=0, sticky="ew", pady=(0, 15))

        # 提示
        self.lbl_hint = ttk.Label(self.main_frame, text="提示: HTML 格式支持实时搜索、缩放及表勾选过滤。", 
                                  foreground="#007bff", font=("Microsoft YaHei", 9))
        self.lbl_hint.grid(row=8, column=0, sticky="w", pady=(5, 0))

        # 底部按钮
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.grid(row=10, column=0, sticky="ew", pady=(20, 0))
        
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="开始导出 ER 表", command=self._start_export, style="Navicat.Primary.TButton").pack(side="right", padx=5)

    def _resize_smooth(self, target_height, step=5, delay=12):
        """平滑调整窗口高度并保持居中"""
        current = self.winfo_height()
        if current == target_height:
            return
        diff = target_height - current
        s = step if diff > 0 else -step
        new_h = current + s
        # 防止越过目标
        if (s > 0 and new_h > target_height) or (s < 0 and new_h < target_height):
            new_h = target_height
        x = (self.winfo_screenwidth() / 2) - (self._base_width / 2)
        y = (self.winfo_screenheight() / 2) - (new_h / 2)
        self.geometry(f'{self._base_width}x{new_h}+{int(x)}+{int(y)}')
        if new_h != target_height:
            self.after(delay, lambda: self._resize_smooth(target_height, step, delay))

    def _on_conn_selected(self, event):
        conn_name = self.cb_conn.get()
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        if not conn_data: return
        
        # 隐藏模式选择
        self.schema_container.grid_forget()
        self._resize_smooth(self._base_height)
        
        progress = ProgressDialog(self, message="正在连接服务器并拉取数据库列表...")
        
        def fetch_dbs():
            try:
                dbs = self.db_ops.get_databases(conn_data)
                self.after(0, lambda: self._on_dbs_fetched(dbs, progress, conn_data))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._on_fetch_error(err_msg, progress))

        threading.Thread(target=fetch_dbs, daemon=True).start()

    def _on_dbs_fetched(self, dbs, progress, conn_data):
        progress.close()
        self.cb_db['values'] = dbs
        if dbs:
            if conn_data.get('db_type') == 'PostgreSQL':
                if 'postgres' in dbs: self.cb_db.set('postgres')
                else: self.cb_db.set(dbs[0])
                self._on_db_selected(None)
            else:
                self.cb_db.set(dbs[0])

    def _on_db_selected(self, event):
        """当数据库被选择时，检查是否需要拉取模式列表"""
        conn_name = self.cb_conn.get()
        conn_data = next((c for c in self.all_connections if c['name'] == conn_name), None)
        if not conn_data or conn_data.get('db_type') != 'PostgreSQL':
            return
            
        selected_db = self.cb_db.get()
        if not selected_db: return
        
        # 显示模式选择 (Grid row 5)
        self.schema_container.grid(row=5, column=0, sticky="ew")
        self._resize_smooth(self._base_height + self._schema_extra)

        def fetch_schemas():
            try:
                schemas = self.db_ops.get_schemas(conn_data, database=selected_db)
                def update():
                    self.cb_schema['values'] = schemas
                    if 'public' in schemas: self.cb_schema.set('public')
                    elif schemas: self.cb_schema.set(schemas[0])
                self.after(0, update)
            except: pass
            
        threading.Thread(target=fetch_schemas, daemon=True).start()

    def _on_fetch_error(self, err_msg, progress):
        progress.close()
        messagebox.showerror("连接失败", f"无法连接服务器: {err_msg}")

    def _start_export(self):
        conn_name = self.cb_conn.get()
        selected_db = self.cb_db.get()
        selected_schema = self.cb_schema.get() if self.schema_container.winfo_ismapped() else None
        
        display_format = self.cb_format.get()
        export_type = self.format_mapping.get(display_format, "html")
        
        if not conn_name or not selected_db:
            messagebox.showwarning("提示", "请先选择连接和数据库")
            return
            
        conn_data = next(c for c in self.all_connections if c['name'] == conn_name)
        
        # 选择保存位置
        ext_map = {"html": ".html", "excel": ".xlsx", "markdown": ".md", "pdf": ".pdf"}
        type_map = {"html": "HTML Files", "excel": "Excel Files", "markdown": "Markdown Files", "pdf": "PDF Files"}
        ext = ext_map[export_type]
        
        filename_base = f"{selected_db}_{selected_schema}" if selected_schema else selected_db
        file_path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(type_map[export_type], f"*{ext}")],
            initialfile=f"{filename_base}_er_diagram{ext}"
        )
        if not file_path: return
        
        progress = ProgressDialog(self, message=f"正在分析 [{selected_db}.{selected_schema if selected_schema else ''}] 的关联关系并生成文件...")
        
        def run_export():
            try:
                # 1. 获取全量表结构 (带模式)
                structures = self.db_ops.get_table_structure(conn_data, database=selected_db, schema=selected_schema)
                # 2. 获取全量外键关系 (ER 图导出暂由 get_relations 处理，目前该方法返回库级关系，
                # 后续可在 exporter 中通过表名集合过滤不属于选定模式的关联)
                relations = self.db_ops.get_relations(conn_data, database=selected_db)
                
                # 3. 执行导出
                if export_type == "html":
                    Exporter.export_er_to_html(structures, relations, file_path)
                elif export_type == "excel":
                    Exporter.export_er_to_excel(structures, relations, file_path)
                elif export_type == "markdown":
                    Exporter.export_er_to_markdown(structures, relations, file_path)
                elif export_type == "pdf":
                    Exporter.export_er_to_pdf(structures, relations, file_path)
                
                self.after(0, lambda: self._on_export_done(progress, True, file_path))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda m=err_msg: self._on_export_done(progress, False, m))
                
        threading.Thread(target=run_export, daemon=True).start()

    def _on_export_done(self, progress, success, result):
        progress.close()
        if success:
            messagebox.showinfo("成功", f"ER 数据已成功导出到:\n{result}")
            self.destroy()
        else:
            messagebox.showerror("导出失败", result)
