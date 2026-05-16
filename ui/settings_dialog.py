import tkinter as tk
from tkinter import ttk, font, messagebox
from core.theme import THEMES, get_theme_colors
from core.ui_style import NavicatStyle, apply_navicat_style, center_window

# 主题颜色定义 - 从统一主题模块导入
THEME_COLORS = {name: {
    "bg": info["bg"], "fg": info["fg"],
    "hb": info["hb"], "accent": info["accent"],
} for name, info in THEMES.items()}

class FontSelectorDialog(tk.Toplevel):
    """独立的字体选择弹出对话框"""
    def __init__(self, parent, all_families, current_font):
        super().__init__(parent)
        self.title("选择系统字体")
        self.resizable(False, False)

        # 居中显示
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 225
        self.geometry(f"400x450+{int(x)}+{int(y)}")

        self.all_families = all_families
        self.filtered_families = all_families.copy()
        self.result = None

        self._init_ui()

        # 初始选中
        if current_font in self.all_families:
            idx = self.all_families.index(current_font)
            self.font_listbox.selection_set(idx)
            self.font_listbox.see(idx)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _init_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # 搜索区域
        search_frame = ttk.Frame(container)
        search_frame.pack(side="top", fill="x", pady=(0, 10))
        ttk.Label(search_frame, text="搜索字体:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind('<KeyRelease>', self._on_search_change)
        self.search_entry.focus_set()

        # 列表区域
        lb_frame = ttk.Frame(container)
        lb_frame.pack(side="top", fill="both", expand=True)
        self.font_listbox = tk.Listbox(lb_frame, font=("Microsoft YaHei", 10),
                                     exportselection=False, activestyle='none')
        self.font_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(lb_frame, orient="vertical", command=self.font_listbox.yview)
        self.font_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.font_listbox.bind("<Double-1>", lambda e: self._confirm())
        self._update_listbox(self.all_families)

        # 按钮区域
        btn_frame = ttk.Frame(container, padding=(0, 10, 0, 0))
        btn_frame.pack(side="bottom", fill="x")
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="确定", command=self._confirm).pack(side="right", padx=5)

    def _update_listbox(self, items):
        self.font_listbox.delete(0, tk.END)
        for item in items:
            self.font_listbox.insert(tk.END, item)

    def _on_search_change(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape'):
            if event.keysym == 'Down': self.font_listbox.focus_set()
            return

        query = self.search_var.get().lower()
        if not query:
            self.filtered_families = self.all_families
        else:
            self.filtered_families = [f for f in self.all_families if query in f.lower()]

        self._update_listbox(self.filtered_families)
        if self.filtered_families:
            self.font_listbox.selection_clear(0, tk.END)
            self.font_listbox.selection_set(0)

    def _confirm(self):
        sel = self.font_listbox.curselection()
        if sel:
            self.result = self.font_listbox.get(sel[0])
            self.destroy()
        else:
            messagebox.showwarning("提示", "请先从列表中选择一个字体")

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_settings):
        super().__init__(parent)
        self.title("系统设置")
        self.resizable(False, False)

        self.result = None
        self.settings = current_settings.copy()
        self.parent_ref = parent

        # 保存打开前的设置，用于取消恢复
        self._original_settings = current_settings.copy()

        # 获取系统字体家族
        families = [f for f in font.families() if not f.startswith('@')]
        self.all_families = sorted(list(set(families)))

        # 应用主题感知的 Navicat 风格
        theme_name = current_settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)

        self._init_ui()

        # 居中显示
        center_window(self, 520, 520)

        # 首次应用预览
        self._apply_preview()

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _init_ui(self):
        # Navicat 风格样式（由 apply_navicat_style 统一配置）

        main = ttk.Frame(self, padding=18)
        main.pack(fill="both", expand=True)

        # ========== 1. 界面风格（下拉选择 + 颜色预览） ==========
        theme_lf = ttk.LabelFrame(main, text="界面风格", padding=(12, 8), style="Navicat.TLabelframe")
        theme_lf.pack(fill="x", pady=(0, 12))

        theme_row = ttk.Frame(theme_lf)
        theme_row.pack(fill="x")

        ttk.Label(theme_row, text="主题:", width=8, anchor="e").pack(side="left")

        self.theme_var = tk.StringVar(value=self.settings.get('theme', '默认'))
        themes = list(THEME_COLORS.keys())
        self.cb_theme = ttk.Combobox(theme_row, values=themes,
                                     textvariable=self.theme_var, state="readonly", width=16)
        self.cb_theme.pack(side="left", padx=(8, 15))
        self.cb_theme.bind("<<ComboboxSelected>>", lambda e: self._apply_preview())

        # 颜色预览色块（3 个小方块：背景/前景/强调色）
        self.color_preview_frame = ttk.Frame(theme_row)
        self.color_preview_frame.pack(side="left", padx=8)

        self.color_swatch_bg = tk.Canvas(self.color_preview_frame, width=20, height=20,
                                         bd=1, relief="solid", highlightthickness=0)
        self.color_swatch_bg.pack(side="left", padx=3)
        self.color_swatch_fg = tk.Canvas(self.color_preview_frame, width=20, height=20,
                                         bd=1, relief="solid", highlightthickness=0)
        self.color_swatch_fg.pack(side="left", padx=3)
        self.color_swatch_accent = tk.Canvas(self.color_preview_frame, width=20, height=20,
                                             bd=1, relief="solid", highlightthickness=0)
        self.color_swatch_accent.pack(side="left", padx=3)

        # 色块标签
        ttk.Label(theme_row, text="背景 / 前景 / 强调", foreground="#888888",
                  font=("Microsoft YaHei", 8)).pack(side="left", padx=(8, 0))

        # ========== 2. 全局字体 ==========
        font_lf = ttk.LabelFrame(main, text="字体设置", padding=(12, 8), style="Navicat.TLabelframe")
        font_lf.pack(fill="x", pady=(0, 12))

        font_row = ttk.Frame(font_lf)
        font_row.pack(fill="x")

        ttk.Label(font_row, text="字体:", width=8, anchor="e").pack(side="left")

        self.font_display_var = tk.StringVar(value=self.settings.get('font_family', 'Microsoft YaHei'))
        self.lbl_curr_font = ttk.Label(font_row, textvariable=self.font_display_var,
                                      font=("Microsoft YaHei", 9, "bold"), foreground="#0078d7")
        self.lbl_curr_font.pack(side="left", padx=(8, 12))

        ttk.Button(font_row, text="更改...", command=self._open_font_selector, width=10).pack(side="left")

        # ========== 3. 字体大小（可输入 Spinbox + 滑块） ==========
        size_row = ttk.Frame(font_lf)
        size_row.pack(fill="x", pady=(10, 0))

        ttk.Label(size_row, text="字号:", width=8, anchor="e").pack(side="left")

        content_size = int(self.settings.get('font_size_content', 10))
        self.font_size_var = tk.IntVar(value=content_size)

        # 可输入的 Spinbox
        self.size_spinbox = ttk.Spinbox(size_row, from_=8, to=20,
                                        textvariable=self.font_size_var, width=4,
                                        command=self._on_size_change)
        self.size_spinbox.pack(side="left", padx=(8, 4))
        self.size_spinbox.bind("<Return>", lambda e: self._on_size_input())
        self.size_spinbox.bind("<FocusOut>", lambda e: self._on_size_input())

        ttk.Label(size_row, text="pt", width=3).pack(side="left")

        # 滑块
        self.size_scale = ttk.Scale(size_row, from_=8, to=20, variable=self.font_size_var,
                                    orient="horizontal", length=200, command=self._on_size_change)
        self.size_scale.pack(side="left", padx=12)

        ttk.Label(size_row, text="(按钮自动-1)", foreground="#888888",
                  font=("Microsoft YaHei", 8)).pack(side="left", padx=(4, 0))

        # ========== 4. 实时预览区域 ==========
        preview_lf = ttk.LabelFrame(main, text="预览效果", padding=(12, 8), style="Navicat.TLabelframe")
        preview_lf.pack(fill="x", pady=(0, 12))

        self.preview_frame = tk.Frame(preview_lf, height=100, bd=1, relief="solid", bg="#f5f5f5")
        self.preview_frame.pack(fill="x")
        self.preview_frame.pack_propagate(False)

        self.preview_label = tk.Label(self.preview_frame, text="示例文本 ABC 123 你好世界",
                                      font=("Microsoft YaHei", 11), bg="#f5f5f5")
        self.preview_label.pack(pady=(15, 8))

        self.preview_btn = tk.Button(self.preview_frame, text="按钮样式", font=("Microsoft YaHei", 9),
                                     relief="raised", padx=15, pady=4)
        self.preview_btn.pack()

        # ========== 底部按钮 ==========
        btn_frame = ttk.Frame(self, padding=(18, 12))
        btn_frame.pack(side="bottom", fill="x")
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="应用", command=self._apply_and_keep, width=10).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="确定", command=self._save, width=10, style="Navicat.Primary.TButton").pack(side="right", padx=6)

    def _on_size_change(self, val):
        """字体大小滑块/Spinbox 变化时更新预览"""
        self._apply_preview()

    def _on_size_input(self):
        """手动输入字号后的校验"""
        try:
            val = self.font_size_var.get()
            val = max(8, min(20, val))
            self.font_size_var.set(val)
        except (tk.TclError, ValueError):
            self.font_size_var.set(10)
        self._apply_preview()

    def _apply_preview(self):
        """实时更新预览区域和颜色色块"""
        theme = self.theme_var.get()
        font_family = self.font_display_var.get()
        try:
            size = int(self.font_size_var.get())
        except (tk.TclError, ValueError):
            size = 10

        colors = THEME_COLORS.get(theme, THEME_COLORS["默认"])
        bg, fg = colors["bg"], colors["fg"]

        # 更新颜色色块
        self.color_swatch_bg.configure(bg=bg)
        self.color_swatch_bg.delete("all")
        self.color_swatch_bg.create_rectangle(0, 0, 18, 18, fill=bg, outline="gray")
        self.color_swatch_fg.configure(bg=fg)
        self.color_swatch_fg.delete("all")
        self.color_swatch_fg.create_rectangle(0, 0, 18, 18, fill=fg, outline="gray")
        self.color_swatch_accent.configure(bg=colors["accent"])
        self.color_swatch_accent.delete("all")
        self.color_swatch_accent.create_rectangle(0, 0, 18, 18, fill=colors["accent"], outline="gray")

        # 更新预览区域
        self.preview_frame.configure(bg=bg)
        self.preview_label.configure(bg=bg, fg=fg, font=(font_family, size))
        self.preview_btn.configure(bg=colors["hb"], fg=fg, font=(font_family, max(size - 1, 8)))

    def _open_font_selector(self):
        """打开独立的字体选择弹窗"""
        dialog = FontSelectorDialog(self, self.all_families, self.font_display_var.get())
        if dialog.result:
            self.font_display_var.set(dialog.result)
            self.lbl_curr_font.configure(font=(dialog.result, 9, "bold"))
            self._apply_preview()

    def _apply_and_keep(self):
        """应用设置但不关闭对话框"""
        self._save_settings_to_result()
        if self.parent_ref and hasattr(self.parent_ref, '_apply_settings'):
            self.parent_ref.settings = self.result.copy()
            self.parent_ref._apply_settings()

    def _save_settings_to_result(self):
        """将当前 UI 状态写入 self.result"""
        try:
            size_content = int(self.font_size_var.get())
        except (tk.TclError, ValueError):
            size_content = 10
        size_content = max(8, min(20, size_content))
        size_btn = max(size_content - 1, 8)

        self.settings['theme'] = self.theme_var.get()
        self.settings['font_family'] = self.font_display_var.get()
        self.settings['font_size_btn'] = str(size_btn)
        self.settings['font_size_content'] = str(size_content)
        self.result = self.settings

    def _save(self):
        """确定并关闭"""
        self._save_settings_to_result()
        if self.parent_ref and hasattr(self.parent_ref, 'settings') and self.result:
            self.parent_ref.settings = self.result.copy()
        self.destroy()

    def _on_cancel(self):
        """取消时恢复原设置"""
        if self.parent_ref and hasattr(self.parent_ref, '_apply_settings'):
            self.parent_ref.settings = self._original_settings.copy()
            self.parent_ref._apply_settings()
        self.destroy()
