"""
Navicat 风格统一样式配置模块

提供统一的样式配置，确保所有对话框保持一致的视觉风格。
参考 Navicat 的设计特点：
- 简洁的分组标签（细线条边框）
- 统一的标签宽度和间距
- 紧凑但合理的布局
- 清晰的图标和按钮样式
- 主题感知（自动跟随主题色变化）
"""

import tkinter as tk
from tkinter import ttk
from core.theme import get_theme_colors


# Navicat 风格常量
class NavicatStyle:
    """Navicat 风格样式配置"""

    # 间距常量
    PADDING_SMALL = 5
    PADDING_MEDIUM = 10
    PADDING_LARGE = 15
    PADDING_XLARGE = 20

    # 标签宽度（用于表单布局）
    LABEL_WIDTH = 10
    LABEL_WIDTH_WIDE = 12

    # 组件尺寸
    COMBOBOX_WIDTH = 40
    ENTRY_WIDTH = 40
    BUTTON_WIDTH = 10

    # 列表高度
    LIST_HEIGHT = 8

    # 日志高度
    LOG_HEIGHT = 5


def apply_navicat_style(root, theme_name="默认"):
    """应用 Navicat 风格到根窗口（主题感知）

    核心样式函数，所有对话框通过此函数统一配置。
    动态使用主题颜色而非硬编码值。

    Args:
        root: tkinter 根窗口或 Toplevel
        theme_name: 主题名称，从 theme.py 获取
    """
    colors = get_theme_colors(theme_name)
    bg = colors["bg"]
    fg = colors["fg"]
    hb = colors["hb"]
    accent = colors["accent"]
    danger = colors["danger"]

    style = ttk.Style()

    # 使用 clam 主题，确保跨平台一致性
    try:
        style.theme_use('clam')
    except:
        pass

    # ==========================================
    # 全局默认样式
    # ==========================================
    style.configure(".", background=bg, foreground=fg)

    # ==========================================
    # TLabelframe — Navicat 风格分组框
    # ==========================================
    style.configure(
        "Navicat.TLabelframe",
        padding=(NavicatStyle.PADDING_MEDIUM, NavicatStyle.PADDING_MEDIUM),
        borderwidth=1,
        relief="solid",
        background=bg,
    )
    style.configure(
        "Navicat.TLabelframe.Label",
        font=("Microsoft YaHei", 9, "bold"),
        foreground=fg,
        background=bg,
    )

    # ==========================================
    # TButton — Navicat 风格按钮
    # ==========================================
    style.configure(
        "Navicat.TButton",
        padding=(NavicatStyle.PADDING_MEDIUM, 5),
        font=("Microsoft YaHei", 9),
        background=hb,
        foreground=fg,
        borderwidth=1,
        focuscolor="none",
    )
    style.map(
        "Navicat.TButton",
        background=[("active", accent), ("pressed", accent)],
        foreground=[("active", "white"), ("pressed", "white")],
    )

    # ==========================================
    # Primary.TButton — Navicat 主要操作按钮（蓝色）
    # ==========================================
    style.configure(
        "Navicat.Primary.TButton",
        padding=(NavicatStyle.PADDING_LARGE, 6),
        font=("Microsoft YaHei", 9, "bold"),
        background=accent,
        foreground="white",
        borderwidth=1,
        focuscolor="none",
    )
    style.map(
        "Navicat.Primary.TButton",
        background=[("active", _darken_color(accent, 0.15)), ("pressed", _darken_color(accent, 0.25))],
    )

    # ==========================================
    # Danger.TButton — 危险操作按钮（红色）
    # ==========================================
    style.configure(
        "Navicat.Danger.TButton",
        padding=(NavicatStyle.PADDING_MEDIUM, 5),
        font=("Microsoft YaHei", 9),
        background=danger,
        foreground="white",
        borderwidth=1,
        focuscolor="none",
    )
    style.map(
        "Navicat.Danger.TButton",
        background=[("active", _darken_color(danger, 0.15)), ("pressed", _darken_color(danger, 0.25))],
    )

    # ==========================================
    # TLabel — Navicat 标签
    # ==========================================
    style.configure(
        "Navicat.TLabel",
        font=("Microsoft YaHei", 9),
        foreground=fg,
        background=bg,
    )

    # ==========================================
    # TEntry — Navicat 输入框
    # ==========================================
    style.configure(
        "Navicat.TEntry",
        padding=4,
        borderwidth=1,
        relief="solid",
        fieldbackground="white" if not _is_dark(bg) else "#3c3c3c",
        foreground=fg,
    )
    style.map(
        "Navicat.TEntry",
        fieldbackground=[("focus", "white" if not _is_dark(bg) else "#505050")],
    )

    # ==========================================
    # TCombobox — Navicat 下拉框
    # ==========================================
    style.configure(
        "Navicat.TCombobox",
        padding=4,
        borderwidth=1,
        relief="solid",
        fieldbackground="white" if not _is_dark(bg) else "#3c3c3c",
        foreground=fg,
        arrowcolor=accent,
    )
    style.map(
        "Navicat.TCombobox",
        fieldbackground=[("focus", "white" if not _is_dark(bg) else "#505050")],
    )

    # ==========================================
    # TNotebook — Navicat 标签页（底部横线指示）
    # ==========================================
    style.configure(
        "Navicat.TNotebook",
        background=hb,
        borderwidth=0,
    )
    style.configure(
        "Navicat.TNotebook.Tab",
        background=hb,
        foreground=fg,
        padding=[NavicatStyle.PADDING_LARGE, 4],
        borderwidth=0,
        focuscolor="none",
    )
    style.map(
        "Navicat.TNotebook.Tab",
        background=[("selected", bg)],
        foreground=[("selected", accent)],
    )

    # ==========================================
    # Treeview — Navicat 树形/表格
    # ==========================================
    style.configure(
        "Navicat.Treeview",
        background=bg,
        fieldbackground=bg,
        foreground=fg,
        font=("Microsoft YaHei", 9),
        rowheight=28,
        borderwidth=0,
    )
    style.configure(
        "Navicat.Treeview.Heading",
        background=hb,
        foreground=fg,
        font=("Microsoft YaHei", 9, "bold"),
        borderwidth=1,
        relief="solid",
    )
    style.map(
        "Navicat.Treeview",
        background=[("selected", colors["select_bg"])],
        foreground=[("selected", "white")],
    )

    # ==========================================
    # Horizontal.TSeparator — Navicat 分割线
    # ==========================================
    style.configure(
        "Navicat.TSeparator",
        background=hb,
    )

    # ==========================================
    # TFrame — Navicat 框架
    # ==========================================
    style.configure("Navicat.TFrame", background=bg)

    # ==========================================
    # TCheckbutton — Navicat 复选框
    # ==========================================
    style.configure(
        "Navicat.TCheckbutton",
        background=bg,
        foreground=fg,
        font=("Microsoft YaHei", 9),
    )
    style.map(
        "Navicat.TCheckbutton",
        background=[("active", bg)],
    )

    # ==========================================
    # TRadiobutton — Navicat 单选框
    # ==========================================
    style.configure(
        "Navicat.TRadiobutton",
        background=bg,
        foreground=fg,
        font=("Microsoft YaHei", 9),
    )

    # 构建根窗口背景
    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(bg=bg)


def _darken_color(hex_color, factor=0.1):
    """将十六进制颜色加深指定因子

    Args:
        hex_color: #rrggbb 格式的颜色
        factor: 加深因子 (0-1)

    Returns:
        加深后的颜色字符串
    """
    try:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    except:
        return hex_color


def _is_dark(bg_color):
    """判断背景色是否为深色

    Args:
        bg_color: 背景色字符串

    Returns:
        True 表示深色背景
    """
    try:
        bg_color = bg_color.lstrip("#")
        r, g, b = int(bg_color[0:2], 16), int(bg_color[2:4], 16), int(bg_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5
    except:
        return False


def calculate_row_height(font_size):
    """计算 Treeview 动态行高

    根据字体大小自适应行高，保持在合理范围内。

    Args:
        font_size: 字体大小（pt）

    Returns:
        行高像素值（28-40px）
    """
    height = int(font_size * 2.2)
    if height < 28:
        height = 28
    if height > 40:
        height = 40
    return height


def update_all_tk_bg(parent, bg_color, fg_color="#333333", font_family="Microsoft YaHei", font_size=10):
    """递归更新所有原生 tk 控件的背景色

    用于 ttk 样式无法覆盖的原生 tk 控件。
    遍历父控件的所有子控件并应用颜色。

    Args:
        parent: 父控件
        bg_color: 背景色
        fg_color: 前景色
        font_family: 字体
        font_size: 字号
    """
    try:
        if isinstance(parent, (tk.Tk, tk.Toplevel, tk.Frame, ttk.Frame)):
            try:
                parent.configure(bg=bg_color)
            except:
                pass
        if isinstance(parent, tk.Label):
            try:
                parent.configure(bg=bg_color, fg=fg_color, font=(font_family, font_size))
            except:
                pass
        if isinstance(parent, (tk.Text, tk.Entry, tk.Listbox)):
            try:
                parent.configure(fg=fg_color, font=(font_family, font_size))
            except:
                pass
        if isinstance(parent, tk.Button):
            try:
                parent.configure(bg=bg_color, fg=fg_color, font=(font_family, font_size))
            except:
                pass
    except:
        pass
    for child in parent.winfo_children():
        update_all_tk_bg(child, bg_color, fg_color, font_family, font_size)


def create_form_row(parent, label_text, widget, row, label_width=None, sticky="w", padx=(0, 10), pady=5):
    """创建标准表单行 - Navicat 风格

    Args:
        parent: 父容器
        label_text: 标签文本
        widget: 要放置的控件（已完成配置的 widget 对象）
        row: 行号
        label_width: 标签宽度（可选，默认使用 LABEL_WIDTH）
        sticky: 对齐方式
        padx: 标签与控件间距
        pady: 上下间距

    Returns:
        label 控件对象
    """
    width = label_width or NavicatStyle.LABEL_WIDTH
    label = ttk.Label(parent, text=label_text, width=width, anchor="e")
    label.grid(row=row, column=0, sticky=sticky, padx=padx, pady=pady)
    widget.grid(row=row, column=1, sticky="ew", pady=pady)
    parent.columnconfigure(1, weight=1)
    return label


def create_button_bar(parent, side="left", padx=5):
    """创建按钮栏容器

    Args:
        parent: 父容器
        side: 按钮排列方向
        padx: 按钮间距

    Returns:
        button frame
    """
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(side=side, fill="x")
    return btn_frame


def create_list_with_scrollbar(parent, height=None, selectmode="multiple"):
    """创建带滚动条的列表框 - Navicat 风格

    Args:
        parent: 父容器
        height: 列表高度（可选）
        selectmode: 选择模式

    Returns:
        (listbox, scrollbar, frame) 元组
    """
    h = height or NavicatStyle.LIST_HEIGHT

    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)

    listbox = tk.Listbox(
        frame,
        selectmode=selectmode,
        height=h,
        font=("Microsoft YaHei", 9),
        borderwidth=1,
        relief="solid",
        activestyle="none"
    )

    vbar = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
    listbox.configure(yscrollcommand=vbar.set)

    listbox.pack(side="left", fill="both", expand=True, padx=(0, 2))
    vbar.pack(side="right", fill="y")

    return listbox, vbar, frame


def create_log_area(parent, height=None):
    """创建日志输出区域 - Navicat 风格

    Args:
        parent: 父容器
        height: 日志区域高度（可选）

    Returns:
        text 控件
    """
    h = height or NavicatStyle.LOG_HEIGHT

    log_text = tk.Text(
        parent,
        height=h,
        font=("Consolas", 9),
        wrap="word",
        state="disabled",
        relief="solid",
        borderwidth=1
    )

    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=scrollbar.set)

    log_text.pack(side="left", fill="both", expand=True, padx=(0, 2))
    scrollbar.pack(side="right", fill="y")

    return log_text


def center_window(window, width=None, height=None):
    """窗口居中显示

    Args:
        window: tkinter 窗口
        width: 窗口宽度（可选，从 window 获取）
        height: 窗口高度（可选，从 window 获取）
    """
    window.update_idletasks()

    if width is None:
        width = window.winfo_width()
    if height is None:
        height = window.winfo_height()

    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)

    window.geometry(f"{width}x{height}+{x}+{y}")
