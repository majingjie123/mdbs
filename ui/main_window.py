import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from models.db_storage import DBStorage
from core.db_operations import DBOperations
from core.ssh_manager import SSHTunnelManager
from core.exporter import Exporter
from core.scratch_manager import ScratchManager
from ui.edit_dialog import EditDialog
from ui.progress_dialog import ProgressDialog
from ui.settings_dialog import SettingsDialog
from ui.db_select_dialog import DatabaseSelectDialog
from ui.export_format_dialog import ExportFormatDialog
from ui.sync_dialog import SyncDialog
from ui.history_window import HistoryWindow
from ui.export_dialog import ExportDialog
from ui.backup_dialog import BackupDialog
from ui.er_export_dialog import ERExportDialog
from ui.sql_workbench import SQLWorkbench
from ui.table_manager import TableManager
from core.theme import get_theme_colors
from core.ui_style import (
    NavicatStyle,
    apply_navicat_style,
    calculate_row_height,
    update_all_tk_bg,
    _is_dark,
    _darken_color,
)
import os
import threading
import concurrent.futures
import pystray
from PIL import Image, ImageDraw

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self._bg = "#ffffe0"
        self._fg = "#333333"
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def update_colors(self, bg_color, fg_color):
        """更新 Tooltip 颜色以匹配当前主题"""
        self._bg = bg_color or "#ffffe0"
        self._fg = fg_color or "#333333"

    def show_tip(self, event=None):
        if self.tip_window or not self.text: return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 27
        y = y + self.widget.winfo_rooty() + 27
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                       background=self._bg, foreground=self._fg,
                       relief=tk.SOLID, borderwidth=1,
                       font=("Microsoft YaHei", 8))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw: tw.destroy()

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MDBS (IDE Mode)")

        # 设置窗口图标（标题栏 + 任务栏）
        ico_path = os.path.join(os.path.dirname(__file__), "..", "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.storage = DBStorage()
        geom = self.storage.get_geometry("main")
        if geom: 
            self.geometry(geom)
        else: 
            # 动态获取屏幕尺寸
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            
            # 设置尺寸为屏幕长宽的三分之一
            win_w = screen_w // 3
            win_h = screen_h // 3
            
            # 居中计算
            x = (screen_w - win_w) // 2
            y = (screen_h - win_h) // 2
            
            self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        self.db_ops = DBOperations()
        self.ssh_manager = SSHTunnelManager()
        self.scratch_manager = ScratchManager()
        self.cancel_event = threading.Event()
        
        self.settings = self.storage.get_settings()
        self.open_workbenches = {}
        self.open_tables = {}
        self.table_cache = {}
        self.search_timer = None
        self.search_entry_widget = None
        self.active_search_node = None
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.sidebar_visible = True
        
        self.tray_icon = None
        self._setup_tray()
        
        self.protocol("WM_DELETE_WINDOW", self._on_exit)
        self.bind("<Unmap>", self._on_window_unmap)
        self._init_ui()
        self._refresh_list()
        self._apply_settings()
        
        self.bind_all("<Control-Shift-S>", lambda e: self._save_all_drafts())

    def _init_ui(self):
        # 1. 顶部菜单行 (Navicat 风格扁平菜单栏)
        self.menu_frame = tk.Frame(self, padx=5, pady=2)
        self.menu_frame.pack(side="top", fill="x")
        
        # 文件菜单
        self.file_menu = tk.Menu(self, tearoff=0)
        self.file_menu.add_command(label="新增连接", command=self._add_conn)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="导入数据...", command=self._import_data)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="导出表结构...", command=self._export_structure)
        self.file_menu.add_command(label="导出 ER 图...", command=self._open_er_export)
        self.file_menu.add_command(label="导出连接 (Excel)", command=self._export_excel)
        self.file_menu.add_command(label="导出为 Navicat (.ncx)", command=self._export_navicat)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="备份 / 恢复...", command=self._backup_restore)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="AI 设置", command=self._open_ai_settings)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self._on_exit)

        btn_file = ttk.Button(self.menu_frame, text="文件", command=lambda: self.file_menu.post(btn_file.winfo_rootx(), btn_file.winfo_rooty() + btn_file.winfo_height()), width=6)
        btn_file.pack(side="left", padx=1)

        # 工具菜单
        self.tools_menu = tk.Menu(self, tearoff=0)
        self.tools_menu.add_command(label="数据库同步", command=self._open_sync)
        self.tools_menu.add_command(label="同步表结构", command=self._open_structure_sync)
        self.tools_menu.add_command(label="同步历史记录", command=self._open_history)

        btn_tools = ttk.Button(self.menu_frame, text="工具", command=lambda: self.tools_menu.post(btn_tools.winfo_rootx(), btn_tools.winfo_rooty() + btn_tools.winfo_height()), width=6)
        btn_tools.pack(side="left", padx=1)

        ttk.Button(self.menu_frame, text="设置", command=self._open_settings, width=6).pack(side="right", padx=1)


        # 分隔线
        self.line_sep = tk.Frame(self, height=1, bg="#dddddd")
        self.line_sep.pack(side="top", fill="x")

        # 3. 主分栏布局
        self.main_paned = ttk.PanedWindow(self, orient="horizontal")
        self.main_paned.pack(fill="both", expand=True, padx=2, pady=2)
        
        # --- 资源管理器容器 ---
        self.sidebar_container = tk.Frame(self.main_paned, width=280)
        self.main_paned.add(self.sidebar_container, weight=0)
        self.sidebar_container.pack_propagate(False) # 锁定宽度
        
        # 2.1 侧边栏标题栏
        self.sidebar_header = tk.Frame(self.sidebar_container)
        self.sidebar_header.pack(side="top", fill="x", pady=2)
        
        self.sidebar_label = tk.Label(self.sidebar_header, text="数据库浏览器", font=("Microsoft YaHei", 9, "bold"))
        self.sidebar_label.pack(side="left", padx=5)
        
        # 切换按钮 (右上角)
        colors = get_theme_colors(self.settings.get('theme', '默认'))
        btn_bg = colors["hb"]
        
        self.btn_toggle = tk.Button(self.sidebar_header, text="◀", bd=0, 
                                   bg=btn_bg, fg=colors["fg"], activebackground=btn_bg,
                                   command=self._toggle_sidebar, cursor="hand2")
        self.btn_toggle.pack(side="right", padx=5)
        Tooltip(self.btn_toggle, "折叠/展开数据库浏览器")
        
        # 2.2 侧边栏内容区
        self.sidebar_frame = tk.Frame(self.sidebar_container)
        self.sidebar_frame.pack(side="top", fill="both", expand=True)
        
        self.tree = ttk.Treeview(self.sidebar_frame, show="tree", selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree_scroll = ttk.Scrollbar(self.sidebar_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.pack(side="right", fill="y")
        
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Configure>", self._on_tree_configure)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Return>", lambda e: self._on_tree_double_click(None))
        self.tree.bind("<Delete>", self._on_tree_delete_key)
        self.tree.bind("<F2>", self._on_tree_f2_key)

        # 右键菜单
        self.conn_menu = tk.Menu(self, tearoff=0)
        self.conn_menu.add_command(label="新建查询", command=self._open_workbench_from_tree)
        self.conn_menu.add_separator()
        self.conn_menu.add_command(label="断开连接", command=self._close_connection)
        self.conn_menu.add_command(label="创建数据库...", command=self._create_database)
        self.conn_menu.add_command(label="刷新数据库列表", command=self._refresh_node)
        self.conn_menu.add_separator()
        self.conn_menu.add_command(label="编辑连接...", command=self._edit_conn)
        self.conn_menu.add_command(label="删除连接", command=self._delete_conn)
        
        self.db_menu = tk.Menu(self, tearoff=0)
        self.db_menu.add_command(label="新建查询", command=self._open_workbench_from_tree)
        self.db_menu.add_separator()
        self.db_menu.add_command(label="同步库结构...", command=self._sync_db_structure)
        self.db_menu.add_separator()
        self.db_menu.add_command(label="刷新", command=self._refresh_node)
        self.db_menu.add_command(label="删除数据库", command=self._delete_database)

        self.obj_menu = tk.Menu(self, tearoff=0)
        self.obj_menu.add_command(label="新建查询", command=self._open_workbench_from_tree)
        self.obj_menu.add_separator()
        self.obj_menu.add_command(label="刷新", command=self._refresh_node)

        self.table_menu = tk.Menu(self, tearoff=0)
        self.table_menu.add_command(label="查看数据", command=self._open_workbench_from_tree)
        self.table_menu.add_separator()
        self.table_menu.add_command(label="查询表结构", command=self._view_table_structure)
        self.table_menu.add_command(label="查看 DDL", command=self._view_table_ddl)
        self.table_menu.add_command(label="修改表结构", command=self._modify_table_structure)
        self.table_menu.add_separator()
        self.table_menu.add_command(label="同步表结构...", command=self._sync_table_structure)
        self.table_menu.add_command(label="📥 导入数据到该表...", command=self._import_to_table)
        self.table_menu.add_separator()
        self.table_menu.add_command(label="复制表名", command=self._copy_table_name)
        self.table_menu.add_command(label="生成 SELECT 语句", command=self._gen_select_stmt)
        self.table_menu.add_separator()
        self.table_menu.add_command(label="新建查询", command=self._open_workbench_from_tree)
        self.table_menu.add_separator()
        self.table_menu.add_command(label="刷新", command=self._refresh_node)

        self.view_menu = tk.Menu(self, tearoff=0)
        self.view_menu.add_command(label="查看视图定义 (DDL)", command=self._view_view_ddl)
        self.view_menu.add_command(label="修改视图", command=self._modify_view)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="复制视图名", command=self._copy_view_name)
        self.view_menu.add_command(label="生成 SELECT 语句", command=self._gen_view_select)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="刷新", command=self._refresh_node)

        self.func_menu = tk.Menu(self, tearoff=0)
        self.func_menu.add_command(label="查看定义 (DDL)", command=self._view_func_ddl)
        self.func_menu.add_command(label="修改函数/过程", command=self._modify_func)
        self.func_menu.add_separator()
        self.func_menu.add_command(label="复制名称", command=self._copy_func_name)
        self.func_menu.add_command(label="测试/调用", command=self._test_func)
        self.func_menu.add_separator()
        self.func_menu.add_command(label="刷新", command=self._refresh_node)

        self.script_menu = tk.Menu(self, tearoff=0)
        self.script_menu.add_command(label="打开脚本", command=lambda: self._on_tree_double_click(None))
        self.script_menu.add_command(label="新建查询", command=self._open_workbench_from_tree)
        self.script_menu.add_command(label="重命名", command=self._rename_script_from_tree)
        self.script_menu.add_separator()
        self.script_menu.add_command(label="刷新列表", command=self._refresh_node)
        self.script_menu.add_command(label="删除脚本文件", command=self._delete_script_from_tree)
        
        # 2.2 右侧：工作区 (Notebook)
        self.workspace = ttk.Notebook(self.main_paned)
        self.main_paned.add(self.workspace, weight=5)
        
        self.tab_menu = tk.Menu(self, tearoff=0)
        self.tab_menu.add_command(label="关闭当前", command=self._close_tab)
        self.tab_menu.add_command(label="关闭其他", command=self._close_other_tabs)
        self.tab_menu.add_command(label="全部关闭", command=self._close_all_tabs)
        self.workspace.bind("<Button-3>", self._show_tab_context_menu)
        
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = tk.Frame(self, height=24)
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar_label = tk.Label(self.status_bar, textvariable=self.status_var,
                                         anchor="w", padx=8, font=("Microsoft YaHei", 8))
        self.status_bar_label.pack(side="left", fill="x", expand=True)

        # 全局快捷键
        self.bind_all("<Control-s>", lambda e: self._on_ctrl_s())
        self.bind_all("<Control-S>", lambda e: self._save_all_drafts())
        self.bind_all("<F5>", lambda e: self._on_f5())
        self.bind_all("<Escape>", lambda e: self._on_escape())

    def _save_all_drafts(self):
        """保存所有已打开的工作台草稿"""
        count = 0
        for bench in self.open_workbenches.values():
            if hasattr(bench, "_save_script"):
                bench._save_script()
                count += 1
        if count > 0:
            self.show_toast(f"已保存 {count} 个工作台")

    def show_toast(self, message, is_error=False):
        """显示非模态 Toast 提示"""
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        
        theme = self.settings.get('theme', '默认')
        colors = get_theme_colors(theme)
        bg, fg = colors["hb"], colors["fg"]
        if is_error:
            bg = colors["danger"]

        label = tk.Label(toast, text=message, bg=bg, fg=fg, padx=20, pady=10, 
                         font=("Microsoft YaHei", 10, "bold"), relief="solid", borderwidth=1)
        label.pack()
        
        self.update_idletasks()
        w, h = label.winfo_reqwidth(), label.winfo_reqheight()
        x = self.winfo_x() + self.winfo_width() - w - 20
        y = self.winfo_y() + self.winfo_height() - h - 50
        toast.geometry(f"{w}x{h}+{x}+{y}")
        self.after(2000, toast.destroy)

    def _on_ctrl_s(self):
        curr = self.workspace.select()
        if not curr: return
        for bench in self.open_workbenches.values():
            if str(bench) == curr:
                if hasattr(bench, '_save_script'):
                    bench._save_script()
                    self.show_toast("脚本已保存")
                break

    def _on_f5(self):
        curr = self.workspace.select()
        if not curr: 
            self._refresh_node()
            return
        # 如果当前是工作台，执行 SQL
        found = False
        for bench in self.open_workbenches.values():
            if str(bench) == curr:
                if hasattr(bench, '_run_query'):
                    bench._run_query()
                    found = True
                break
        if not found:
            self._refresh_node()

    def _on_stop_query(self):
        curr = self.workspace.select()
        if not curr: return
        for bench in self.open_workbenches.values():
            if str(bench) == curr:
                if hasattr(bench, '_stop_query'):
                    bench._stop_query()
                    self.show_toast("查询已停止", is_error=True)
                break

    def _on_escape(self):
        if self.search_entry_widget:
            self._clear_search()
            self._hide_search_entry()

    def _show_tab_context_menu(self, event):
        element = self.workspace.identify(event.x, event.y)
        if "label" in element:
            index = self.workspace.index(f"@{event.x},{event.y}")
            self.workspace.select(index)
            self.tab_menu.post(event.x_root, event.y_root)

    def _close_tab(self):
        curr = self.workspace.select()
        if not curr: return
        for key, obj in list(self.open_workbenches.items()):
            if str(obj) == curr:
                # 保存 AI 聊天历史
                if hasattr(obj, 'chat_panel') and hasattr(obj.chat_panel, 'save_on_close'):
                    try:
                        obj.chat_panel.save_on_close()
                    except Exception:
                        pass
                del self.open_workbenches[key]
                break
        for key, obj in list(self.open_tables.items()):
            if str(obj) == curr:
                del self.open_tables[key]
                break
        self.workspace.forget(curr)

    def _close_other_tabs(self):
        curr = self.workspace.select()
        for tab in self.workspace.tabs():
            if str(tab) != str(curr):
                for key, obj in list(self.open_workbenches.items()):
                    if str(obj) == str(tab):
                        if hasattr(obj, 'chat_panel') and hasattr(obj.chat_panel, 'save_on_close'):
                            try:
                                obj.chat_panel.save_on_close()
                            except Exception:
                                pass
                        del self.open_workbenches[key]
                        break
                for key, obj in list(self.open_tables.items()):
                    if str(obj) == str(tab):
                        del self.open_tables[key]
                        break
                self.workspace.forget(tab)

    def _close_all_tabs(self):
        for tab in self.workspace.tabs():
            for key, obj in list(self.open_workbenches.items()):
                if str(obj) == str(tab):
                    if hasattr(obj, 'chat_panel') and hasattr(obj.chat_panel, 'save_on_close'):
                        try:
                            obj.chat_panel.save_on_close()
                        except Exception:
                            pass
                    del self.open_workbenches[key]
                    break
            for key, obj in list(self.open_tables.items()):
                if str(obj) == str(tab):
                    del self.open_tables[key]
                    break
            self.workspace.forget(tab)

    def _on_tree_double_click(self, event):
        if event:
            item_id = self.tree.identify_row(event.y)
        else:
            sel = self.tree.selection()
            item_id = sel[0] if sel else None
            
        if not item_id: return
        tags = self.tree.item(item_id, "tags")
        
        if "connection" in tags:
            self._fetch_databases(item_id)
        elif "database" in tags:
            # 获取连接类型
            conn_id = int(item_id.split(":")[0])
            conn_data = self.storage.get_connection(conn_id)
            if conn_data.get('db_type') == 'PostgreSQL':
                self._fetch_schemas(item_id)
            else:
                self._fetch_db_objects(item_id)
        elif "schema" in tags:
            self._fetch_db_objects(item_id)
        elif "table" in tags or "view" in tags or "new_query" in tags:
            self._open_workbench_from_tree(item_id)
        elif "query_file" in tags:
            self._open_saved_script(item_id)

    def _on_tree_delete_key(self, event):
        """键盘 Delete 键处理：根据选中节点类型删除连接/数据库/脚本"""
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        tags = self.tree.item(item_id, "tags")
        if "connection" in tags:
            self._delete_conn()
        elif "database" in tags:
            self._delete_database()
        elif "query_file" in tags:
            self._delete_script_from_tree()

    def _on_tree_f2_key(self, event):
        """键盘 F2 键处理：重命名脚本"""
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        tags = self.tree.item(item_id, "tags")
        if "query_file" in tags:
            self._rename_script_from_tree()

    def _fetch_databases(self, conn_node_id):
        self._clear_search()
        conn_id = int(conn_node_id)
        conn_data = self.storage.get_connection(conn_id)
        self.status_var.set(f"正在拉取 {conn_data['name']} 的数据库...")
        
        def run():
            try:
                dbs = self.db_ops.get_databases(conn_data)
                self.after(0, lambda: self._on_dbs_fetched(conn_node_id, dbs))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", f"获取库列表失败: {e}"))
            finally:
                self.after(0, lambda: self.status_var.set("就绪"))
        threading.Thread(target=run, daemon=True).start()

    def _on_dbs_fetched(self, conn_node_id, dbs):
        # 清除占位加载节点 + 旧数据
        for child in self.tree.get_children(conn_node_id): self.tree.delete(child)
        for db in dbs:
            iid = f"{conn_node_id}:{db}"
            self.tree.insert(conn_node_id, "end", iid=iid, text=f"🗄️ {db}", tags=("database",))
            # 恢复展开状态
            saved = getattr(self, '_saved_expand', set())
            if iid in saved:
                self.tree.item(iid, open=True)
        self._saved_expand = set()
        self.tree.item(conn_node_id, open=True)

    def _fetch_schemas(self, db_node_id):
        parts = db_node_id.split(":")
        conn_id, db_name = int(parts[0]), parts[1]
        conn_data = self.storage.get_connection(conn_id)
        self.status_var.set(f"正在加载 {db_name} 的模式 (Schema)...")

        def run():
            try:
                schemas = self.db_ops.get_schemas(conn_data, database=db_name)
                self.after(0, lambda: self._on_schemas_fetched(db_node_id, schemas))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", f"加载模式失败: {e}"))
            finally:
                self.after(0, lambda: self.status_var.set("就绪"))
        threading.Thread(target=run, daemon=True).start()

    def _on_schemas_fetched(self, db_node_id, schemas):
        # 清除占位加载节点 + 旧数据
        for child in self.tree.get_children(db_node_id): self.tree.delete(child)
        for s in schemas:
            iid = f"{db_node_id}:{s}"
            self.tree.insert(db_node_id, "end", iid=iid, text=f"🏺 {s}", tags=("schema",))
            # 恢复展开状态
            saved = getattr(self, '_saved_expand', set())
            if iid in saved:
                self.tree.item(iid, open=True)
        self._saved_expand = set()
        self.tree.item(db_node_id, open=True)

    def _fetch_db_objects(self, node_id):
        parts = node_id.split(":")
        conn_id = int(parts[0])
        db_name = parts[1]
        schema_name = parts[2] if len(parts) > 2 else None
        
        conn_data = self.storage.get_connection(conn_id)
        display_name = schema_name or db_name
        self.status_var.set(f"正在加载 {display_name} 的对象（并行查询中...）")

        def run():
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                    ft_tables = pool.submit(self.db_ops.get_tables, conn_data, database=db_name, schema=schema_name)
                    ft_views = pool.submit(self.db_ops.get_views, conn_data, database=db_name, schema=schema_name)
                    ft_funcs = pool.submit(self.db_ops.get_functions, conn_data, database=db_name, schema=schema_name)
                    tables = ft_tables.result()
                    views = ft_views.result()
                    funcs = ft_funcs.result()
                self.after(0, lambda: self._on_objects_fetched(node_id, tables, views, funcs))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", f"加载对象失败: {e}"))
            finally:
                self.after(0, lambda: self.status_var.set("就绪"))
        threading.Thread(target=run, daemon=True).start()

    def _on_objects_fetched(self, parent_node_id, tables, views, funcs):
        # 清除占位加载节点 + 旧数据
        for child in self.tree.get_children(parent_node_id): self.tree.delete(child)
        saved = getattr(self, '_saved_expand', set())
        
        # 文件夹图标 📂
        q_folder = self.tree.insert(parent_node_id, "end", iid=f"{parent_node_id}:queries", text="📂 查询", tags=("folder",))
        if f"{parent_node_id}:queries" in saved:
            self.tree.item(q_folder, open=True)
        parts = parent_node_id.split(":")
        conn_id, db_name = int(parts[0]), parts[1]
        conn_data = self.storage.get_connection(conn_id)
        saved_scripts = self.scratch_manager.list_scripts(conn_data['name'], db_name)
        for s in saved_scripts:
            # 脚本图标 📜
            self.tree.insert(q_folder, "end", iid=f"{parent_node_id}:file:{s['path']}", text=f"📜 {s['name']}", tags=("query_file",))

        t_folder = self.tree.insert(parent_node_id, "end", iid=f"{parent_node_id}:tables", text="📂 表", tags=("folder",))
        if f"{parent_node_id}:tables" in saved:
            self.tree.item(t_folder, open=True)
        self.table_cache[t_folder] = tables
        self.tree.insert(t_folder, "end", iid=f"{t_folder}:search", text="🔍 过滤表名...", tags=("search_placeholder",))
        for t in tables: 
            # 数据表图标 📊
            self.tree.insert(t_folder, "end", text=f"📊 {t['name'] if isinstance(t, dict) else t}", tags=("table",))
        
        v_folder = self.tree.insert(parent_node_id, "end", iid=f"{parent_node_id}:views", text="📂 视图", tags=("folder",))
        if f"{parent_node_id}:views" in saved:
            self.tree.item(v_folder, open=True)
        for v in views: 
            # 视图图标 🖼️
            self.tree.insert(v_folder, "end", text=f"🖼️ {v}", tags=("view",))
        
        f_folder = self.tree.insert(parent_node_id, "end", iid=f"{parent_node_id}:funcs", text="📂 函数/过程", tags=("folder",))
        if f"{parent_node_id}:funcs" in saved:
            self.tree.item(f_folder, open=True)
        for f in funcs: 
            # 函数图标 ⚙️
            icon = "⚙️" if f['type'] == 'PROCEDURE' else "ƒ"
            self.tree.insert(f_folder, "end", text=f"{icon} {f['name']}", tags=("func",), values=(f['type'],))
        
        self._saved_expand = set()
        self.tree.item(parent_node_id, open=True)

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            self._hide_search_entry()
            return
            
        tags = self.tree.item(item_id, "tags")
        is_open = self.tree.item(item_id, "open")
        has_children = bool(self.tree.get_children(item_id))
        
        # 1. 切换展开/折叠状态
        if has_children or any(t in tags for t in ("connection", "database", "schema", "folder")):
            # 如果当前是折叠的，且没有子节点 → 自动加载
            if not is_open and not has_children:
                if "connection" in tags:
                    self._fetch_databases(item_id)
                    # 显示占位节点让用户知道在加载
                    if not self.tree.get_children(item_id):
                        self.tree.insert(item_id, "end", iid=f"{item_id}:loading", 
                                         text="⏳ 加载中...", tags=("loading",))
                    self.tree.item(item_id, open=True)
                elif "database" in tags:
                    conn_id = int(item_id.split(":")[0])
                    conn_data = self.storage.get_connection(conn_id)
                    if conn_data and conn_data.get('db_type') == 'PostgreSQL':
                        self._fetch_schemas(item_id)
                    else:
                        self._fetch_db_objects(item_id)
                    if not self.tree.get_children(item_id):
                        self.tree.insert(item_id, "end", iid=f"{item_id}:loading", 
                                         text="⏳ 加载中...", tags=("loading",))
                    self.tree.item(item_id, open=True)
                elif "schema" in tags:
                    self._fetch_db_objects(item_id)
                    if not self.tree.get_children(item_id):
                        self.tree.insert(item_id, "end", iid=f"{item_id}:loading", 
                                         text="⏳ 加载中...", tags=("loading",))
                    self.tree.item(item_id, open=True)
                else:
                    self.tree.item(item_id, open=not is_open)
            else:
                self.tree.item(item_id, open=not is_open)
            
        # 2. 处理搜索占位符
        if "search_placeholder" in tags:
            self._show_search_entry(item_id)
        else:
            self._hide_search_entry()

    def _on_tree_configure(self, event):
        if self.search_entry_widget:
            self._update_search_entry_pos()

    def _show_search_entry(self, item_id):
        if self.active_search_node == item_id and self.search_entry_widget:
            self.search_entry_widget.focus_set()
            return
            
        self._hide_search_entry()
        self.active_search_node = item_id
        bbox = self.tree.bbox(item_id)
        if not bbox: return
        x, y, w, h = bbox
        
        colors = get_theme_colors(self.settings.get('theme', '默认'))
        bg, fg = colors["bg"], colors["fg"]

        self.search_entry_widget = tk.Entry(self.tree, textvariable=self.search_var, 
                                          bg=bg, fg=fg, insertbackground=fg,
                                          relief="flat", borderwidth=0, font=("Microsoft YaHei", 9))
        self.search_entry_widget.place(x=x+2, y=y+1, width=w-25, height=h-2)
        self.search_entry_widget.focus_set()
        
        self.search_clear_btn = tk.Button(self.tree, text="⨉", bg=bg, fg="gray", 
                                        relief="flat", command=self._clear_search,
                                        font=("Arial", 8), cursor="hand2", bd=0)
        self.search_clear_btn.place(x=x+w-22, y=y+1, width=20, height=h-2)
        
        self.search_entry_widget.bind("<FocusOut>", lambda e: self.after(200, self._check_hide_search))
        self.search_entry_widget.bind("<Return>", lambda e: self.focus_set())
        self.search_entry_widget.bind("<Escape>", lambda e: self._clear_search())

    def _hide_search_entry(self):
        if self.search_entry_widget:
            try: self.search_entry_widget.destroy()
            except: pass
            self.search_entry_widget = None
        if hasattr(self, 'search_clear_btn') and self.search_clear_btn:
            try: self.search_clear_btn.destroy()
            except: pass
            self.search_clear_btn = None
        self.active_search_node = None

    def _check_hide_search(self):
        focus = self.focus_get()
        if focus not in (self.search_entry_widget, self.search_clear_btn):
            self._hide_search_entry()

    def _update_search_entry_pos(self):
        if not self.active_search_node: return
        bbox = self.tree.bbox(self.active_search_node)
        if bbox:
            x, y, w, h = bbox
            self.search_entry_widget.place(x=x+2, y=y+1, width=w-25, height=h-2)
            if hasattr(self, 'search_clear_btn'):
                self.search_clear_btn.place(x=x+w-22, y=y+1, width=20, height=h-2)
        else:
            self._hide_search_entry()

    def _on_search_change(self, *args):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, self._filter_tables)

    def _clear_search(self):
        self.search_var.set("")
        self._filter_tables()
        if self.search_entry_widget:
            self.search_entry_widget.delete(0, tk.END)
        self.focus_set()

    def _filter_tables(self):
        query = self.search_var.get().strip().lower()
        folder_iid = None
        if self.active_search_node:
            folder_iid = self.tree.parent(self.active_search_node)
        
        if not query:
            if folder_iid and folder_iid in self.table_cache:
                self._update_tree_folder(folder_iid, self.table_cache[folder_iid])
            else:
                for f_iid, tables in self.table_cache.items():
                    self._update_tree_folder(f_iid, tables)
            return

        targets = [folder_iid] if folder_iid else list(self.table_cache.keys())
        for f_iid in targets:
            if not self.tree.exists(f_iid) or f_iid not in self.table_cache: continue
            tables = self.table_cache[f_iid]
            filtered = [t for t in tables if query in (t['name'] if isinstance(t, dict) else t).lower()]
            self._update_tree_folder(f_iid, filtered)

    def _update_tree_folder(self, folder_iid, item_list):
        if not self.tree.exists(folder_iid): return
        search_node_id = f"{folder_iid}:search"
        sel = self.tree.selection()
        sel_text = self.tree.item(sel[0], "text") if sel else None
        
        for child in self.tree.get_children(folder_iid):
            if child != search_node_id: self.tree.delete(child)
        
        if not item_list and self.search_var.get():
            self.tree.insert(folder_iid, "end", text="（未找到匹配的项）", tags=("hint",))
        else:
            for item in item_list:
                name = item['name'] if isinstance(item, dict) else item
                node = self.tree.insert(folder_iid, "end", text=name, tags=("table",))
                if item == sel_text or name == sel_text: self.tree.selection_set(node)

    def _open_saved_script(self, node_id):
        parts = node_id.split(":file:")
        if len(parts) < 2: return
        db_context_id = parts[0]
        file_path = parts[1]
        script_name = self.tree.item(node_id, "text")
        
        if file_path in self.open_workbenches:
            try:
                self.workspace.select(self.open_workbenches[file_path])
                return
            except: del self.open_workbenches[file_path]
            
        db_parts = db_context_id.split(":")
        conn_id, db_name = int(db_parts[0]), db_parts[1]
        
        # 显式传递 script_path 确保 SQLWorkbench 识别为已有脚本
        bench = SQLWorkbench(self.workspace, conn_id, db_name=db_name, 
                            on_save_callback=lambda: self._fetch_db_objects(db_context_id),
                            cancel_event=self.cancel_event,
                            script_path=file_path)
                            
        self.workspace.add(bench, text=f"Q: {script_name}")
        self.workspace.select(bench)
        self.open_workbenches[file_path] = bench

    def _delete_script_from_tree(self):
        sel = self.tree.selection()
        if not sel: return
        node_id = sel[0]
        parts = node_id.split(":file:")
        if len(parts) < 2: return
        file_path = parts[1]
        if messagebox.askyesno("确认", f"确定彻底删除？"):
            self.scratch_manager.delete_script_path(file_path)
            self._fetch_db_objects(parts[0])

    def _rename_script_from_tree(self):
        sel = self.tree.selection()
        if not sel: return
        node_id = sel[0]
        parts = node_id.split(":file:")
        if len(parts) < 2: return
        old_path = parts[1]
        old_name = self.tree.item(node_id, "text")
        new_title = simpledialog.askstring("重命名", "新名称:", initialvalue=old_name, parent=self)
        if new_title and new_title != old_name:
            if self.scratch_manager.rename_script(old_path, new_title):
                self._fetch_db_objects(parts[0])

    def _open_workbench_from_tree(self, node_id=None):
        if not node_id:
            sel = self.tree.selection()
            if not sel: return
            node_id = sel[0]
        
        db_name, conn_id, schema_name = self._get_node_db_context(node_id)
        if not db_name or not conn_id: return
        
        tags = self.tree.item(node_id, "tags")
        conn_data = self.storage.get_connection(conn_id)
        db_type = conn_data.get('db_type', 'MySQL')
        
        initial_sql = None
        tab_title = f"SQL: {db_name}"
        
        if "table" in tags or "view" in tags:
            # 提取表/视图名（去掉图标前缀）
            raw_text = self.tree.item(node_id, "text")
            table_name = raw_text
            for icon in ["📊 ", "🖼️ ", "📜 "]:
                if table_name.startswith(icon):
                    table_name = table_name[len(icon):]
                    break
            
            # 构建 SELECT 语句
            if db_type == "MySQL":
                initial_sql = f"SELECT * FROM `{table_name}` LIMIT 1000;"
            else:
                if schema_name:
                    initial_sql = f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 1000;'
                else:
                    initial_sql = f'SELECT * FROM "{table_name}" LIMIT 1000;'
            
            tab_title = table_name
        
        bench = SQLWorkbench(self.workspace, conn_id, db_name=db_name, schema_name=schema_name,
                             on_save_callback=lambda: self._fetch_db_objects(node_id),
                             load_draft=False, initial_sql=initial_sql)
        self.workspace.add(bench, text=tab_title)
        self.workspace.select(bench)
        self.open_workbenches[f"new_{id(bench)}"] = bench

    def _close_connection(self):
        """断开选中的连接：关闭隧道、收起节点、关闭相关标签页并清空子节点"""
        cid = self._get_selected_id()
        if not cid: return
        
        # 获取连接名称用于提示
        node_id = str(cid)
        conn_name = self.tree.item(node_id, "text") if self.tree.exists(node_id) else str(cid)
        
        # 1. 停止 SSH 隧道
        self.ssh_manager.stop_tunnel(cid)
        
        # 2. 自动关闭所有属于该连接的标签页和对话框
        # 2.1 处理 SQL 工作台 (Notebook 标签页)
        for key, obj in list(self.open_workbenches.items()):
            if hasattr(obj, 'conn_id') and obj.conn_id == cid:
                # 保存 AI 聊天历史
                if hasattr(obj, 'chat_panel') and hasattr(obj.chat_panel, 'save_on_close'):
                    try: obj.chat_panel.save_on_close()
                    except: pass
                try:
                    self.workspace.forget(obj)
                except:
                    pass
                del self.open_workbenches[key]

        # 2.2 处理表管理器 (Notebook 标签页)
        for key, obj in list(self.open_tables.items()):
            if hasattr(obj, 'conn_id') and obj.conn_id == cid:
                try:
                    self.workspace.forget(obj)
                except:
                    pass
                del self.open_tables[key]

        # 2.3 处理其他关联的顶级窗口 (如视图/函数管理器等)
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                if hasattr(child, 'conn_id') and child.conn_id == cid:
                    try:
                        child.destroy()
                    except:
                        pass
                # 针对那些没有 conn_id 但可能正在使用该连接的向导（可选，暂不强制）

        # 3. 获取 Treeview 节点并收起
        if self.tree.exists(node_id):
            self.tree.item(node_id, open=False)
            # 清空子节点 (数据库列表)
            for child in self.tree.get_children(node_id):
                self.tree.delete(child)
        
        self.show_toast(f"{conn_name} 已断开，相关标签页已关闭")

    def _refresh_node(self):
        sel = self.tree.selection()
        if not sel: return
        node_id = sel[0]
        tags = self.tree.item(node_id, "tags")
        # 保存展开状态（通过子节点 iid 记录哪些是展开的）
        self._saved_expand = {
            child for child in self.tree.get_children(node_id)
            if self.tree.item(child, "open")
        }
        if "connection" in tags:
            self._fetch_databases(node_id)
        elif "database" in tags:
            self._fetch_db_objects(node_id)
        elif "folder" in tags:
            self._saved_expand = set()
            self._fetch_db_objects(self.tree.parent(node_id))

    def _refresh_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        for c in self.storage.get_all_connections():
            self.tree.insert("", "end", iid=str(c['id']), text=c['name'], tags=("connection",))

    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel: return None
        curr = sel[0]
        while curr:
            if "connection" in self.tree.item(curr, "tags"): return int(curr)
            curr = self.tree.parent(curr)
        return None

    def _apply_settings(self):
        """应用主题样式并实时刷新全界面（Navicat 风格）"""
        self.update_idletasks()
        style = ttk.Style()
        style.theme_use('clam')
        
        theme = self.settings.get('theme', '默认')
        font_family = self.settings.get('font_family', 'Microsoft YaHei')
        size_btn = int(self.settings.get('font_size_btn', 10))
        size_content = int(self.settings.get('font_size_content', 10))
        
        colors = get_theme_colors(theme)
        bg, fg, hb = colors["bg"], colors["fg"], colors["hb"]
        accent, danger = colors["accent"], colors["danger"]
        select_bg, grid_color = colors["select_bg"], colors["grid_color"]
        stripe_color = colors["stripe_color"]
        
        self.configure(bg=bg)
        
        # 定义通用字体对象
        main_font = (font_family, size_content)
        btn_font = (font_family, size_btn)
        
        # 使用 ui_style 模块计算动态行高
        dynamic_row_height = calculate_row_height(size_content)
        
        # ========== 1. 全局 ttk 样式 ==========
        style.configure(".", background=bg, foreground=fg, font=main_font)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        
        # Treeview — 带网格线和斑马纹支持
        style.configure("Treeview", 
                        background=bg, 
                        fieldbackground=bg, 
                        foreground=fg, 
                        font=main_font,
                        rowheight=dynamic_row_height,
                        gridcolor=grid_color,
                        borderwidth=0)
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        
        style.configure("Treeview.Heading", 
                        background=hb, 
                        foreground=fg, 
                        font=(font_family, size_content, "bold"),
                        rowheight=dynamic_row_height + 4,
                        borderwidth=1,
                        relief="solid")
        
        style.map("Treeview",
                  background=[('selected', select_bg)],
                  foreground=[('selected', 'white')])
        
        # Notebook 标签页
        style.configure("TNotebook", background=hb, borderwidth=0)
        style.configure("TNotebook.Tab", background=hb, foreground=fg, padding=[NavicatStyle.PADDING_LARGE, 4], borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", bg)], foreground=[("selected", accent)])
        
        # 按钮样式
        style.configure("TButton", font=btn_font, background=hb, foreground=fg, borderwidth=1)
        style.map("TButton",
                  background=[("active", accent), ("pressed", accent)],
                  foreground=[("active", "white"), ("pressed", "white")])
        style.configure("Primary.TButton", background=accent, foreground="white", font=btn_font, borderwidth=1)
        style.map("Primary.TButton",
                  background=[("active", _darken_color(accent, 0.15))])
        style.configure("Danger.TButton", background=danger, foreground="white", font=btn_font, borderwidth=1)
        style.map("Danger.TButton",
                  background=[("active", _darken_color(danger, 0.15))])
            
        # ========== 2. 递归更新原生 Tkinter 控件 ==========
        update_all_tk_bg(self, bg, fg, font_family, size_content)
        
        # ========== 3. 特殊控件处理 ==========
        # 状态栏
        if hasattr(self, 'status_bar'):
            self.status_bar.configure(bg=hb)
        if hasattr(self, 'status_bar_label'):
            self.status_bar_label.configure(bg=hb, fg=fg)
        # 菜单栏
        if hasattr(self, 'menu_frame'):
            self.menu_frame.configure(bg=hb)
        # 分隔线
        if hasattr(self, 'line_sep'):
            self.line_sep.configure(bg=hb)
        # 侧边栏
        if hasattr(self, 'sidebar_container'):
            self.sidebar_container.configure(bg=bg)
        if hasattr(self, 'sidebar_header'):
            self.sidebar_header.configure(bg=hb)
        if hasattr(self, 'sidebar_label'):
            self.sidebar_label.configure(bg=hb, fg=fg)
        if hasattr(self, 'sidebar_frame'):
            self.sidebar_frame.configure(bg=bg)
        if hasattr(self, 'btn_toggle'):
            self.btn_toggle.configure(bg=hb, fg=fg, activebackground=bg)
        # 更新菜单栏子控件背景
        if hasattr(self, 'menu_frame'):
            for child in self.menu_frame.winfo_children():
                if isinstance(child, ttk.Button):
                    pass  # ttk 样式已处理
                elif isinstance(child, tk.Frame):
                    child.configure(bg=hb)
        
        # 更新 Tooltip 颜色
        for w in self.winfo_children():
            self._update_tooltips(w, hb, fg)

        # ========== 4. 通知子组件 ==========
        for bench in list(self.open_workbenches.values()):
            try:
                if hasattr(bench, '_apply_settings'):
                    bench.settings = self.settings
                    bench._apply_settings()
                elif hasattr(bench, '_apply_theme'):
                    bench.settings = self.settings
                    bench._apply_theme()
            except: pass
            
        for manager in list(self.open_tables.values()):
            try:
                if hasattr(manager, '_apply_theme'):
                    manager.settings = self.settings
                    manager._apply_theme()
            except: pass

    def _update_tooltips(self, parent, bg_color, fg_color):
        """递归更新所有 Tooltip 实例的颜色"""
        for child in parent.winfo_children():
            if hasattr(child, 'update_colors'):
                try:
                    child.update_colors(bg_color, fg_color)
                except:
                    pass
            self._update_tooltips(child, bg_color, fg_color)

    def _add_conn(self):
        d = EditDialog(self)
        if d.result:
            self.storage.add_connection(d.result)
            self._refresh_list()
            self.show_toast("连接已添加")

    def _edit_conn(self):
        cid = self._get_selected_id()
        if cid:
            d = EditDialog(self, self.storage.get_connection(cid))
            if d.result:
                self.ssh_manager.stop_tunnel(cid)
                self.storage.update_connection(cid, d.result)
                self._refresh_list()
                self.show_toast("连接已更新")

    def _create_database(self):
        """弹出对话框并创建新数据库"""
        cid = self._get_selected_id()
        if not cid: return
        conn_data = self.storage.get_connection(cid)
        db_type = conn_data.get('db_type', 'MySQL')
        
        from ui.create_db_dialog import CreateDatabaseDialog
        d = CreateDatabaseDialog(self, db_type=db_type)
        self.wait_window(d)
        
        if not d.result: return
        db_params = d.result
        db_name = db_params['name']
        
        def run():
            success, msg = self.db_ops.create_database(conn_data, db_params)
            if success:
                self.after(0, lambda: self.show_toast(f"数据库 {db_name} 创建成功"))
                # 刷新当前连接节点
                self.after(0, self._refresh_node)
            else:
                self.after(0, lambda: messagebox.showerror("错误", f"创建数据库失败: {msg}"))
        
        threading.Thread(target=run, daemon=True).start()

    def _delete_conn(self):
        cid = self._get_selected_id()
        if cid and messagebox.askyesno("确认", "确定删除？"):
            self.ssh_manager.stop_tunnel(cid)
            self.storage.delete_connection(cid)
            self._refresh_list()
            self.show_toast("连接已删除", is_error=True)

    def _delete_database(self):
        """删除选中的数据库，包含二次确认"""
        sel = self.tree.selection()
        if not sel: return
        node_id = sel[0]
        db_name, conn_id, _ = self._get_node_db_context(node_id)
        if not conn_id or not db_name: return
        
        if not messagebox.askyesno("危险确认", f"确定要永久删除数据库 [{db_name}] 吗？\n此操作不可恢复！", parent=self):
            return
            
        conn_data = self.storage.get_connection(conn_id)
        
        def run():
            success, msg = self.db_ops.delete_database(conn_data, db_name)
            if success:
                self.after(0, lambda: self.show_toast(f"数据库 {db_name} 已删除", is_error=True))
                # 刷新父连接节点
                parent_node = self.tree.parent(node_id)
                self.after(0, lambda: self._fetch_databases(parent_node))
            else:
                self.after(0, lambda: messagebox.showerror("错误", f"删除数据库失败: {msg}"))
        
        threading.Thread(target=run, daemon=True).start()

    def _show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            tags = self.tree.item(item_id, "tags")
            if "connection" in tags:
                self.conn_menu.post(event.x_root, event.y_root)
            elif "database" in tags:
                self.db_menu.post(event.x_root, event.y_root)
            elif "query_file" in tags:
                self.script_menu.post(event.x_root, event.y_root)
            elif "table" in tags:
                self.table_menu.post(event.x_root, event.y_root)
            elif "view" in tags:
                self.view_menu.post(event.x_root, event.y_root)
            elif "func" in tags:
                self.func_menu.post(event.x_root, event.y_root)
            elif "search_placeholder" in tags:
                pass
            else:
                self.obj_menu.post(event.x_root, event.y_root)

    def _open_history(self):
        HistoryWindow(self)

    def _open_sync(self):
        SyncDialog(self)

    def _open_er_export(self):
        ERExportDialog(self)

    def _export_structure(self):
        ExportDialog(self)

    def _import_data(self):
        """打开数据导入对话框（无预选表）"""
        from ui.import_dialog import ImportDialog
        ImportDialog(self)

    def _import_to_table(self):
        """打开数据导入对话框并预选当前表"""
        from ui.import_dialog import ImportDialog
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        tags = self.tree.item(item_id, "tags")
        if "table" not in tags:
            return

        db_name, conn_id, schema_name = self._get_node_db_context(item_id)
        if not conn_id or not db_name:
            return

        conn_data = self.storage.get_connection(conn_id)
        # 从节点 ID 中提取表名（格式: conn_id:table_name 或 conn_id:schema_name:table_name）
        parts = item_id.split(":")
        if len(parts) >= 3:
            table_name = parts[-1]
        elif len(parts) == 2:
            table_name = parts[-1]
        else:
            table_name = self._strip_icon(self.tree.item(item_id, "text"))

        ImportDialog(self, conn_data=conn_data, database=db_name,
                     schema=schema_name, table_name=table_name)

    def _open_settings(self):
        d = SettingsDialog(self, self.settings)
        if d.result:
            self.settings = d.result
            self.storage.save_settings(self.settings)
            self._apply_settings()

    def _open_ai_settings(self):
        from ui.ai.ai_settings_dialog import AISettingsDialog

        def _on_configs_changed():
            """AI 配置有变化时，刷新所有已打开工作台的 chat_panel 配置列表"""
            for bench in self.open_workbenches.values():
                if hasattr(bench, 'chat_panel') and hasattr(bench.chat_panel, '_load_configs'):
                    try:
                        bench.chat_panel._load_configs()
                    except Exception:
                        pass

        AISettingsDialog(self, on_configs_changed=_on_configs_changed)

    def _export_excel(self):
        conns = self.storage.get_all_connections()
        if conns:
            path = filedialog.asksaveasfilename(defaultextension=".xlsx")
            if path: 
                Exporter.export_connections_to_excel(conns, path)
                self.show_toast("导出成功")

    def _export_navicat(self):
        conns = self.storage.get_all_connections()
        if conns:
            path = filedialog.asksaveasfilename(defaultextension=".ncx")
            if path: 
                Exporter.export_to_navicat(conns, path)
                self.show_toast("导出成功")

    def _backup_restore(self):
        """打开备份/恢复对话框"""
        BackupDialog(self)

    def _view_table_ddl(self):
        sel = self.tree.selection()
        if not sel: return
        table_node = sel[0]
        table_name = self._strip_icon(self.tree.item(table_node, "text"))
        db_name, conn_id, schema_name = self._get_node_db_context(table_node)
        if not conn_id: return
        conn_data = self.storage.get_connection(conn_id)
        
        def run():
            try:
                # 获取 DDL，支持模式名
                ddl = self.db_ops.get_table_ddl(conn_data, table_name, database=db_name, schema=schema_name)
                self.after(0, lambda: self._open_ddl_in_workbench(table_name, ddl, conn_id, db_name, schema_name))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", f"获取 DDL 失败: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _open_ddl_in_workbench(self, obj_name, ddl, conn_id, db_name, schema_name=None):
        """直接在 SQL 工作台的新标签页中打开 DDL"""
        bench = SQLWorkbench(self.workspace, conn_id, db_name=db_name, schema_name=schema_name, load_draft=False)
        bench.editor.insert("1.0", ddl)
        bench._highlight_syntax()
        self.workspace.add(bench, text=f"DDL: {obj_name}")
        self.workspace.select(bench)
        self.open_workbenches[f"new_{id(bench)}"] = bench

    def _show_ddl_dialog(self, obj_name, ddl, conn_id, db_name, schema_name=None, title=None):
        ddl_win = tk.Toplevel(self)
        display_name = f"{schema_name}.{obj_name}" if schema_name else obj_name
        ddl_win.title(title or f"查看 DDL - {display_name}")
        ddl_win.geometry("800x600")
        ddl_win.transient(self)
        
        colors = get_theme_colors(self.settings.get('theme', '默认'))
        bg, fg = colors["bg"], colors["fg"]
        ddl_win.configure(bg=bg)

        text_area = tk.Text(ddl_win, padx=10, pady=10, font=("Consolas", 10))
        text_area.pack(fill="both", expand=True, padx=10, pady=10)
        text_area.insert("1.0", ddl)
        text_area.configure(bg=bg, fg=fg, insertbackground=fg)
        
        btn_frame = tk.Frame(ddl_win, bg=bg, pady=10)
        btn_frame.pack(side="bottom", fill="x")
        
        def copy_ddl():
            self.clipboard_clear()
            self.clipboard_append(ddl)
            self.show_toast("已复制到剪贴板")

        def open_in_bench():
            bench = SQLWorkbench(self.workspace, conn_id, db_name=db_name, schema_name=schema_name, load_draft=False)
            bench.editor.insert("1.0", ddl)
            bench._highlight_syntax()
            self.workspace.add(bench, text=f"DDL: {obj_name}")
            self.workspace.select(bench)
            self.open_workbenches[f"new_{id(bench)}"] = bench
            ddl_win.destroy()

        ttk.Button(btn_frame, text="复制到剪贴板", command=copy_ddl).pack(side="right", padx=10)
        ttk.Button(btn_frame, text="在工作台中打开", command=open_in_bench).pack(side="right", padx=10)
        ttk.Button(btn_frame, text="关闭", command=ddl_win.destroy).pack(side="right", padx=10)

    def _view_view_ddl(self):
        sel = self.tree.selection()
        if not sel: return
        node = sel[0]
        name = self._strip_icon(self.tree.item(node, "text"))
        db_name, conn_id, schema_name = self._get_node_db_context(node)
        if not conn_id: return
        conn_data = self.storage.get_connection(conn_id)
        
        def run():
            try:
                # PG 下需要模式名
                full_view_name = f"{schema_name}.{name}" if schema_name else name
                ddl = self.db_ops.get_view_ddl(conn_data, full_view_name, database=db_name)
                self.after(0, lambda: self._open_ddl_in_workbench(name, ddl, conn_id, db_name, schema_name))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _modify_view(self):
        sel = self.tree.selection()
        if not sel: return
        node = sel[0]
        name = self._strip_icon(self.tree.item(node, "text"))
        db_name, conn_id, schema_name = self._get_node_db_context(node)
        if not conn_id: return
        
        # 传递带模式的全名给对话框
        actual_view_name = f"{schema_name}.{name}" if schema_name else name
        from ui.view_manager_dialog import ViewManagerDialog
        ViewManagerDialog(self, conn_id, db_name, actual_view_name)

    def _copy_view_name(self):
        sel = self.tree.selection()
        if not sel: return
        name = self._strip_icon(self.tree.item(sel[0], "text"))
        self.clipboard_clear()
        self.clipboard_append(name)
        self.show_toast(f"已复制视图名: {name}")

    def _gen_view_select(self):
        self._gen_select_stmt()

    def _view_func_ddl(self):
        sel = self.tree.selection()
        if not sel: return
        node = sel[0]
        name = self._strip_icon(self.tree.item(node, "text"))
        func_type = self.tree.item(node, "values")[0]
        db_name, conn_id, schema_name = self._get_node_db_context(node)
        if not conn_id: return
        conn_data = self.storage.get_connection(conn_id)
        
        def run():
            try:
                # PG 下函数通常也需要模式限定
                full_func_name = f"{schema_name}.{name}" if schema_name else name
                ddl = self.db_ops.get_function_ddl(conn_data, full_func_name, func_type=func_type, database=db_name)
                self.after(0, lambda: self._open_ddl_in_workbench(name, ddl, conn_id, db_name, schema_name))

            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("错误", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _modify_func(self):
        sel = self.tree.selection()
        if not sel: return
        node = sel[0]
        name = self._strip_icon(self.tree.item(node, "text"))
        func_type = self.tree.item(node, "values")[0]
        db_name, conn_id, schema_name = self._get_node_db_context(node)
        if not conn_id: return
        
        actual_func_name = f"{schema_name}.{name}" if schema_name else name
        from ui.function_manager_dialog import FunctionManagerDialog
        FunctionManagerDialog(self, conn_id, db_name, actual_func_name, func_type)

    def _copy_func_name(self):
        sel = self.tree.selection()
        if not sel: return
        name = self._strip_icon(self.tree.item(sel[0], "text"))
        self.clipboard_clear()
        self.clipboard_append(name)
        self.show_toast(f"已复制名称: {name}")

    def _test_func(self):
        sel = self.tree.selection()
        if not sel: return
        node = sel[0]
        name = self._strip_icon(self.tree.item(node, "text"))
        func_type = self.tree.item(node, "values")[0]
        db_name, conn_id, schema_name = self._get_node_db_context(node)
        if not conn_id: return
        
        # SQL 生成也需要考虑模式
        full_name = f'"{schema_name}"."{name}"' if schema_name else f'"{name}"'
        sql = f"SELECT {full_name}(...);" if func_type == "FUNCTION" else f"CALL {full_name}(...);"
        
        bench = SQLWorkbench(self.workspace, conn_id, db_name=db_name, schema_name=schema_name, load_draft=False)
        bench.editor.insert("1.0", sql)
        bench._highlight_syntax()
        self.workspace.add(bench, text=f"Test: {name}")
        self.workspace.select(bench)
        self.open_workbenches[f"new_{id(bench)}"] = bench

    @staticmethod
    def _strip_icon(text):
        """从资源树节点的显示文本中剥离 Emoji/图标前缀，提取纯名称"""
        for prefix in ['📊 ', '🖼️ ', '⚙️ ', 'ƒ ', '🗄️ ', '🏺 ', '📜 ', '🔍 ']:
            if text.startswith(prefix):
                return text[len(prefix):]
        return text

    def _get_node_db_context(self, node_id):
        """向上追溯获取连接 ID、数据库名以及可选的模式 (Schema) 名 (修复 Emoji 干扰)"""
        curr = node_id
        db_name, conn_id, schema_name = None, None, None

        while curr:
            tags = self.tree.item(curr, "tags")
            # 优先从 IID 或 values 提取，避免受 Text 中图标干扰
            if "schema" in tags:
                parts = curr.split(":")
                if len(parts) >= 3: schema_name = parts[2]
                else:
                    vals = self.tree.item(curr, "values")
                    schema_name = vals[1] if (vals and len(vals)>1) else (vals[0] if vals else self.tree.item(curr, "text"))
            elif "database" in tags:
                parts = curr.split(":")
                if len(parts) >= 2: db_name = parts[1]
                else:
                    vals = self.tree.item(curr, "values")
                    db_name = vals[0] if vals else self.tree.item(curr, "text")

                parent = self.tree.parent(curr)
                if parent and parent.isdigit():
                    conn_id = int(parent)
                break
            curr = self.tree.parent(curr)
        return db_name, conn_id, schema_name
    def _copy_table_name(self):
        sel = self.tree.selection()
        if not sel: return
        table_name = self._strip_icon(self.tree.item(sel[0], "text"))
        self.clipboard_clear()
        self.clipboard_append(table_name)
        self.show_toast(f"已复制表名: {table_name}")

    def _gen_select_stmt(self):
        sel = self.tree.selection()
        if not sel: return
        table_node = sel[0]
        table_name = self._strip_icon(self.tree.item(table_node, "text"))
        db_name, conn_id, schema_name = self._get_node_db_context(table_node)
        if not conn_id: return
        conn_data = self.storage.get_connection(conn_id)
        db_type = conn_data.get('db_type', 'MySQL')
        
        if db_type == "MySQL":
            sql = f"SELECT * FROM `{table_name}` LIMIT 100;"
        else:
            # PostgreSQL 处理模式
            full_name = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
            sql = f"SELECT * FROM {full_name} LIMIT 100;"
            
        bench = SQLWorkbench(self.workspace, conn_id, db_name=db_name, schema_name=schema_name, load_draft=False)
        bench.editor.insert("1.0", sql)
        bench._highlight_syntax()
        self.workspace.add(bench, text=f"SQL: {table_name}")
        self.workspace.select(bench)
        self.open_workbenches[f"new_{id(bench)}"] = bench

    def _view_table_structure(self):
        self._open_table_manager(read_only=True)

    def _modify_table_structure(self):
        self._open_table_manager(read_only=False)

    def _open_table_manager(self, read_only=True):
        sel = self.tree.selection()
        if not sel: return
        table_node = sel[0]
        table_name = self._strip_icon(self.tree.item(table_node, "text"))
        db_name, conn_id, schema_name = self._get_node_db_context(table_node)
        if not conn_id: return
        
        # 使用 schema 增强 tab_key 唯一性
        tab_key = f"table_{conn_id}_{db_name}_{schema_name or 'public'}_{table_name}"
        if tab_key in self.open_tables:
            try:
                self.workspace.select(self.open_tables[tab_key])
                return
            except:
                del self.open_tables[tab_key]

        manager = TableManager(self.workspace, conn_id, db_name, table_name, schema_name=schema_name, read_only=read_only)
        title = f"{'👁' if read_only else '✏️'} {table_name}"
        self.workspace.add(manager, text=title)
        self.workspace.select(manager)
        self.open_tables[tab_key] = manager

    def _toggle_sidebar(self):
        """折叠/展开左侧资源管理器，工作台自动扩展填满空间"""
        try:
            if self.sidebar_visible:
                # 1. 记录折叠前的实际宽度
                self.last_sidebar_width = self.sidebar_container.winfo_width()
                
                # 2. 隐藏标题文字和树状列表
                self.sidebar_frame.pack_forget()
                self.sidebar_label.pack_forget()
                
                # 3. 调整容器宽度并强制移动 PanedWindow 的分栏条
                self.sidebar_container.configure(width=35)
                try:
                    self.main_paned.sashpos(0, 35)
                except:
                    pass
                
                self.btn_toggle.config(text="▶")
            else:
                # 1. 恢复之前记录的宽度（默认 280）
                w = getattr(self, 'last_sidebar_width', 280)
                if w < 100: w = 280
                
                self.sidebar_container.configure(width=w)
                
                # 2. 重新显示组件
                self.sidebar_label.pack(side="left", padx=5)
                self.sidebar_frame.pack(side="top", fill="both", expand=True)
                
                # 3. 恢复分栏条位置
                try:
                    self.main_paned.sashpos(0, w)
                except:
                    pass
                    
                self.btn_toggle.config(text="◀")
            
            self.sidebar_visible = not self.sidebar_visible
        except:
            pass

    def _on_exit(self):
        """退出应用程序时的清理工作"""
        try:
            # 1. 停止托盘图标
            if hasattr(self, 'tray_icon') and self.tray_icon:
                try: self.tray_icon.stop()
                except: pass

            # 2. 保存窗口位置和大小
            if hasattr(self, 'storage'):
                self.storage.save_geometry("main", self.geometry())
            
            # 3. 停止所有后台任务
            if hasattr(self, 'cancel_event'):
                self.cancel_event.set()
            
            # 4. 停止所有 SSH 隧道
            if hasattr(self, 'ssh_manager'):
                self.ssh_manager.stop_all_tunnels()
            
            # 5. 销毁所有工作台
            if hasattr(self, 'open_workbenches'):
                for bench in list(self.open_workbenches.values()):
                    try:
                        if hasattr(bench, 'chat_panel') and hasattr(bench.chat_panel, 'save_on_close'):
                            bench.chat_panel.save_on_close()
                    except:
                        pass
                    try:
                        if hasattr(bench, 'destroy'):
                            bench.destroy()
                    except:
                        pass
            if hasattr(self, 'open_tables'):
                for manager in list(self.open_tables.values()):
                    try:
                        if hasattr(manager, 'destroy'):
                            manager.destroy()
                    except:
                        pass
        except:
            pass
        finally:
            self.destroy()

    def _create_placeholder_icon(self):
        """创建一个简单的图标 (蓝底白字 "D")"""
        image = Image.new('RGB', (64, 64), color=(73, 109, 137))
        draw = ImageDraw.Draw(image)
        # 绘制一个白色的 "D" 占位
        try:
            draw.text((20, 10), "D", fill=(255, 255, 255))
        except:
            # 如果没有默认字体，画个矩形代替
            draw.rectangle([16, 16, 48, 48], outline=(255, 255, 255), width=4)
        return image

    def _setup_tray(self):
        """初始化系统托盘图标"""
        menu = (
            pystray.MenuItem('显示主窗口', self._restore_from_tray, default=True),
            pystray.MenuItem('退出', self._on_exit)
        )
        
        # 尝试寻找图标文件，如果没有则生成占位符
        icon_path = os.path.join(os.path.dirname(__file__), "..", "icon.ico")
        if os.path.exists(icon_path):
            try:
                image = Image.open(icon_path)
            except:
                image = self._create_placeholder_icon()
        else:
            image = self._create_placeholder_icon()
            
        self.tray_icon = pystray.Icon("mdbs", image, "MDBS", menu)
        # 在后台线程运行托盘，避免阻塞 Tkinter
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _on_window_unmap(self, event):
        """监听窗口最小化事件"""
        if event.widget == self and self.wm_state() == 'iconic':
            self.withdraw() # 从任务栏移除
            self.show_toast("应用已最小化到系统托盘")

    def _restore_from_tray(self, icon=None, item=None):
        """托盘菜单恢复指令"""
        self.after(0, self._do_restore)

    def _do_restore(self):
        """执行窗口恢复逻辑"""
        self.deiconify()
        self.state('normal')
        self.focus_force()

    def _open_structure_sync(self):
        """打开结构同步向导 (独立模式)"""
        SyncDialog(self, sync_mode="structure")

    def _sync_db_structure(self):
        """右键菜单：同步库结构"""
        sel = self.tree.selection()
        if not sel: return
        node_id = sel[0]
        db_name, conn_id, _ = self._get_node_db_context(node_id)
        if conn_id:
            SyncDialog(self, source_conn_id=conn_id, source_db=db_name, sync_mode="structure")

    def _sync_table_structure(self):
        """右键菜单：同步表结构"""
        sel = self.tree.selection()
        if not sel: return
        node_id = sel[0]
        table_name = self._strip_icon(self.tree.item(node_id, "text"))
        db_name, conn_id, _ = self._get_node_db_context(node_id)
        if conn_id:
            SyncDialog(self, source_conn_id=conn_id, source_db=db_name, 
                       selected_tables=[table_name], sync_mode="structure")
