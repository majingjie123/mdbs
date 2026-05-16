import tkinter as tk
from tkinter import ttk
from core.ui_style import apply_navicat_style

class ExportFormatDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        # 获取父窗口的主题设置
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)
        self.title("选择导出格式")
        self.resizable(False, False)

        # 增加高度防止按钮被遮挡
        width, height = 320, 220
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        
        # 获取主窗口背景色
        self.bg_color = "#f0f0f0"
        if hasattr(parent, 'settings'):
            self.bg_color = parent.settings.get('bg_color', '#f0f0f0')
        self.configure(bg=self.bg_color)
        
        self.result = None
        self._init_ui()
        
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _init_ui(self):
        # 使用 tk.Frame 以便支持背景颜色
        f = tk.Frame(self, bg=self.bg_color, padx=20, pady=20)
        f.pack(fill="both", expand=True)
        
        tk.Label(f, text="请选择导出文件的格式:", bg=self.bg_color, font=("Microsoft YaHei", 10, "bold")).pack(pady=10)
        
        self.format_var = tk.StringVar(value="html")
        
        # 单选按钮
        tk.Radiobutton(f, text="HTML 交互报告", variable=self.format_var, value="html", 
                       bg=self.bg_color, activebackground=self.bg_color).pack(anchor="w", pady=5)
        tk.Radiobutton(f, text="Markdown 文档", variable=self.format_var, value="markdown", 
                       bg=self.bg_color, activebackground=self.bg_color).pack(anchor="w", pady=5)
        tk.Radiobutton(f, text="PDF 文档", variable=self.format_var, value="pdf", 
                       bg=self.bg_color, activebackground=self.bg_color).pack(anchor="w", pady=5)
        tk.Radiobutton(f, text="Excel 文档 (单Sheet)", variable=self.format_var, value="excel_single", 
                       bg=self.bg_color, activebackground=self.bg_color).pack(anchor="w", pady=5)
        
        # 底部按钮区域
        btn_frame = tk.Frame(self, bg=self.bg_color, padx=10, pady=10)
        btn_frame.pack(side="bottom", fill="x")
        
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="确定", command=self._on_ok, style="Navicat.Primary.TButton").pack(side="right", padx=5)

    def _on_ok(self):
        self.result = self.format_var.get()
        self.destroy()
