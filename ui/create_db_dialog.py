import tkinter as tk
from tkinter import ttk, messagebox
from core.ui_style import apply_navicat_style

class CreateDatabaseDialog(tk.Toplevel):
    def __init__(self, parent, db_type="MySQL"):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title("创建数据库")
        self.result = None
        self.db_type = db_type
        
        # 居中显示，适度增大尺寸
        self.geometry("450x380")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self._init_ui()
        self._center_window()

    def _init_ui(self):
        # 容器
        main_frame = ttk.Frame(self, padding=30)
        main_frame.pack(fill="both", expand=True)
        
        # 配置列权重，使输入框可拉伸
        main_frame.columnconfigure(1, weight=1)
        
        # 1. 数据库名称
        ttk.Label(main_frame, text="数据库名称:").grid(row=0, column=0, sticky="w", pady=10)
        self.ent_name = ttk.Entry(main_frame)
        self.ent_name.grid(row=0, column=1, sticky="ew", pady=10, padx=(10, 0))
        self.ent_name.focus_set()

        if self.db_type == "MySQL":
            # 2. 字符集
            ttk.Label(main_frame, text="字符集 (Charset):").grid(row=1, column=0, sticky="w", pady=10)
            self.cb_charset = ttk.Combobox(main_frame, values=["utf8mb4", "utf8", "latin1", "gbk"], state="readonly")
            self.cb_charset.set("utf8mb4")
            self.cb_charset.grid(row=1, column=1, sticky="ew", pady=10, padx=(10, 0))
            
            # 3. 排序规则
            ttk.Label(main_frame, text="排序规则 (Collation):").grid(row=2, column=0, sticky="w", pady=10)
            self.cb_collate = ttk.Combobox(main_frame, values=["utf8mb4_general_ci", "utf8mb4_unicode_ci", "utf8mb4_bin"], state="readonly")
            self.cb_collate.set("utf8mb4_general_ci")
            self.cb_collate.grid(row=2, column=1, sticky="ew", pady=10, padx=(10, 0))
        else:
            # PostgreSQL
            # 2. 编码
            ttk.Label(main_frame, text="编码 (Encoding):").grid(row=1, column=0, sticky="w", pady=10)
            self.cb_encoding = ttk.Combobox(main_frame, values=["UTF8", "LATIN1", "SQL_ASCII"], state="readonly")
            self.cb_encoding.set("UTF8")
            self.cb_encoding.grid(row=1, column=1, sticky="ew", pady=10, padx=(10, 0))
            
            # 3. 所有者 (可选)
            ttk.Label(main_frame, text="所有者 (Owner):").grid(row=2, column=0, sticky="w", pady=10)
            self.ent_owner = ttk.Entry(main_frame)
            self.ent_owner.grid(row=2, column=1, sticky="ew", pady=10, padx=(10, 0))

        # 按钮区
        btn_frame = ttk.Frame(self, padding=(0, 0, 0, 20))
        btn_frame.pack(side="bottom", fill="x")
        
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=20)
        ttk.Button(btn_frame, text="确定", command=self._on_ok, style="Navicat.Primary.TButton").pack(side="right")

    def _on_ok(self):
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showwarning("警告", "请输入数据库名称")
            return
            
        if self.db_type == "MySQL":
            self.result = {
                "name": name,
                "charset": self.cb_charset.get().strip() or "utf8mb4",
                "collation": self.cb_collate.get().strip() or "utf8mb4_general_ci"
            }
        else:
            self.result = {
                "name": name,
                "encoding": self.cb_encoding.get().strip() or "UTF8",
                "owner": self.ent_owner.get().strip()
            }
        self.destroy()

    def _center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
