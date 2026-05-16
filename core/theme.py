"""统一主题定义 - 所有 UI 组件的单一样式数据源

包含全部 9 个主题的所有颜色键，各 UI 模块通过 get_theme_colors() 获取颜色。
使用此模块后，新增主题只需在此添加定义，各 UI 组件自动适配。
"""

# 完整主题颜色定义：9 主题 × 9 个颜色键
THEMES = {
    "默认": {
        "bg": "#ffffff", "fg": "#333333", "hb": "#f2f2f2",
        "accent": "#007bff", "danger": "#dc3545",
        "grid_color": "#d0d0d0", "stripe_color": "#f5f5f5",
        "select_bg": "#0078d7",
        "syntax_keyword": "#0000ff", "syntax_string": "#a52a2a", "syntax_comment": "#008000",
    },
    "暗黑模式": {
        "bg": "#2b2b2b", "fg": "#e0e0e0", "hb": "#3c3f41",
        "accent": "#3e6c93", "danger": "#933e3e",
        "grid_color": "#121212", "stripe_color": "#323232",
        "select_bg": "#4b6eaf",
        "syntax_keyword": "#569cd6", "syntax_string": "#ce9178", "syntax_comment": "#6a9955",
    },
    "黑客绿": {
        "bg": "#000000", "fg": "#00ff00", "hb": "#001a00",
        "accent": "#004400", "danger": "#440000",
        "grid_color": "#003300", "stripe_color": "#000800",
        "select_bg": "#004400",
        "syntax_keyword": "#00ff00", "syntax_string": "#00ff00", "syntax_comment": "#008800",
    },
    "护眼绿": {
        "bg": "#c7edcc", "fg": "#2c3e50", "hb": "#b8e2b8",
        "accent": "#27ae60", "danger": "#c0392b",
        "grid_color": "#a8d8ae", "stripe_color": "#b8e2b8",
        "select_bg": "#27ae60",
        "syntax_keyword": "#1a6e35", "syntax_string": "#8b4513", "syntax_comment": "#5b8a5b",
    },
    "清新蓝": {
        "bg": "#f0f8ff", "fg": "#2c3e50", "hb": "#e1efff",
        "accent": "#3498db", "danger": "#e74c3c",
        "grid_color": "#d0dce8", "stripe_color": "#e5f0fa",
        "select_bg": "#3498db",
        "syntax_keyword": "#1a5fa6", "syntax_string": "#8b4513", "syntax_comment": "#5b8a5b",
    },
    "深海蓝": {
        "bg": "#001f3f", "fg": "#ffffff", "hb": "#003366",
        "accent": "#0074d9", "danger": "#ff4136",
        "grid_color": "#001a33", "stripe_color": "#00294d",
        "select_bg": "#0074d9",
        "syntax_keyword": "#5dade2", "syntax_string": "#e67e22", "syntax_comment": "#229954",
    },
    "优雅紫": {
        "bg": "#f5f0f9", "fg": "#4a235a", "hb": "#ebe0f5",
        "accent": "#8e44ad", "danger": "#c0392b",
        "grid_color": "#ddd5e8", "stripe_color": "#ede5f5",
        "select_bg": "#8e44ad",
        "syntax_keyword": "#7d3c98", "syntax_string": "#a04000", "syntax_comment": "#117a65",
    },
    "落日橙": {
        "bg": "#fff5ee", "fg": "#5d4037", "hb": "#ffe4e1",
        "accent": "#d35400", "danger": "#c0392b",
        "grid_color": "#e8ddd5", "stripe_color": "#f8eee5",
        "select_bg": "#d35400",
        "syntax_keyword": "#c0392b", "syntax_string": "#a04000", "syntax_comment": "#1e8449",
    },
    "樱花粉": {
        "bg": "#fff0f5", "fg": "#5d4037", "hb": "#ffe4e1",
        "accent": "#e91e63", "danger": "#c0392b",
        "grid_color": "#e8d5dd", "stripe_color": "#f8e5ed",
        "select_bg": "#e91e63",
        "syntax_keyword": "#c0392b", "syntax_string": "#a04000", "syntax_comment": "#1e8449",
    },
}

# 全局主题名称列表
THEME_NAMES = list(THEMES.keys())


def get_theme_colors(theme_name):
    """获取指定主题的颜色字典，不存在的主题回退到 '默认'

    返回颜色字典，包含以下键：
        bg, fg, hb, accent, danger,
        grid_color, stripe_color, select_bg,
        syntax_keyword, syntax_string, syntax_comment
    """
    return THEMES.get(theme_name, THEMES["默认"])


def is_dark_theme(theme_name):
    """判断是否为深色主题（用于需要特别处理的场景）"""
    dark_themes = {"暗黑模式", "黑客绿", "深海蓝"}
    return theme_name in dark_themes
