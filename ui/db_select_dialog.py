import tkinter as tk
from tkinter import ttk
from core.ui_style import apply_navicat_style

class DatabaseSelectDialog(tk.Toplevel):
    def __init__(self, parent, databases):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title("选择数据库")
        self.resizable(False, False)

        # 居中
        width, height = 300, 350
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        
        self.result = None
        self._init_ui(databases)
        
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _init_ui(self, databases):
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        
        ttk.Label(f, text="请选择要导出的数据库:").pack(pady=5)
        
        # 搜索框
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self._filter_list())
        ttk.Entry(f, textvariable=self.search_var).pack(fill="x", pady=5)
        
        # 列表框
        list_frame = ttk.Frame(f)
        list_frame.pack(fill="both", expand=True)
        
        self.listbox = tk.Listbox(list_frame)
        self.listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
        self.all_dbs = databases
        self._fill_listbox(databases)
        
        # 底部按钮
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="确认", command=self._on_ok, style="Navicat.Primary.TButton").pack(side="right", padx=5)
        
        # 绑定双击确认
        self.listbox.bind("<Double-1>", lambda e: self._on_ok())

    def _fill_listbox(self, items):
        self.listbox.delete(0, tk.END)
        for item in sorted(items):
            self.listbox.insert(tk.END, item)

    def _filter_list(self):
        search_term = self.search_var.get().lower()
        filtered = [db for db in self.all_dbs if search_term in db.lower()]
        self._fill_listbox(filtered)

    def _on_ok(self):
        selection = self.listbox.curselection()
        if selection:
            self.result = self.listbox.get(selection[0])
            self.destroy()
