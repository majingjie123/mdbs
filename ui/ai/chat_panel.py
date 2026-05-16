"""AI 聊天面板，嵌入 SQL 工作台右侧"""

import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
import json
from datetime import datetime
from core.theme import get_theme_colors, is_dark_theme
from models.db_storage import DBStorage
from core.ai.client import AIClient
from core.ai.markdown_renderer import MarkdownRenderer
from ui.ai.session_wizard import SessionWizard


class AIChatPanel(ttk.Frame):
    """AI 聊天面板，包含配置选择、消息区、输入区"""

    # 需要拦截的快捷键，防止冒泡到 SQL 工作台触发执行
    _BLOCKED_KEYS = ('<F5>', '<Control-Return>', '<Control-s>', '<Control-f>',
                     '<Control-space>', '<Alt-slash>', '<Escape>')

    def __init__(self, parent, conn_data=None, db_ops=None, db_name=None,
                 schema_name=None, conn_id=None, script_path=None):
        super().__init__(parent)
        self.storage = DBStorage()
        self.conn_data = conn_data
        self.db_ops = db_ops
        self.db_name = db_name or ''
        self.schema_name = schema_name
        self.conn_id = conn_id or (conn_data.get('id') if conn_data else None)
        self.script_path = script_path or ''

        # 对话状态
        self.messages = []
        self._user_msg_ranges = []  # [(start, end, msg_index), ...] 用于定位可编辑的用户消息
        self.table_context = ''
        self.table_context_summary = ''
        self.is_streaming = False
        self.chunk_queue = queue.Queue()
        self._current_assistant_text = ''

        # 配置
        self._ai_configs = []
        self._active_config = None

        self._init_ui()
        self._load_configs()
        self._load_history()
        self.settings = self.storage.get_settings()
        self.after(100, self._apply_theme)

    def _apply_theme(self):
        """应用统一主题系统颜色"""
        theme = self.settings.get('theme', '默认')
        colors = get_theme_colors(theme)
        self._colors = colors
        self._is_dark = is_dark_theme(theme)
        bg, fg = colors["bg"], colors["fg"]
        hb = colors["hb"]
        accent = colors["accent"]

        # 面板自身背景（ttk.Frame 不支持直接设置 bg，由内部 tk.Frame 子组件覆盖）

        # 消息区
        if hasattr(self, 'msg_area'):
            self.msg_area.config(bg=bg, fg=fg)
            # 占位标签的样式
            self.msg_area.tag_config("placeholder", foreground=fg, font=("Microsoft YaHei", 10, "bold"))

        # 输入区
        if hasattr(self, 'input_text'):
            self.input_text.config(bg=hb if self._is_dark else bg, fg=fg,
                                    insertbackground=fg)

        # 配置消息区标签颜色
        self._setup_msg_tags()

        # 配置按钮
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Button):
                pass  # ttk Button 由 style 控制
            elif isinstance(widget, (tk.Button, tk.Label, tk.Frame)):
                try:
                    widget.config(bg=bg, fg=fg)
                except: pass

        # 更新状态指示器（异步安全）
        try:
            if hasattr(self, '_status_label') and self._status_label.winfo_exists():
                has_c = self.table_context != ''
                color = accent if has_c else (fg if self._is_dark else "#bdbdbd")
                self._status_label.config(fg=color)
        except: pass

    def _init_ui(self):
        """构建聊天面板界面"""
        # self.configure(width=320)  # 移除固定宽度，由父级 PanedWindow 管理
        # self.pack_propagate(False)

        # ---- 头部 ----
        header = tk.Frame(self, padx=5, pady=3)
        header.pack(side="top", fill="x")

        ttk.Label(header, text="AI:", font=("Microsoft YaHei", 9)).pack(side="left")
        self.config_var = tk.StringVar()
        self.config_combo = ttk.Combobox(header, textvariable=self.config_var,
                                          state="readonly", width=14)
        self.config_combo.pack(side="left", padx=3)
        self.config_combo.bind("<<ComboboxSelected>>", self._on_config_changed)

        ttk.Button(header, text="⚙", width=3, command=self._open_session_wizard).pack(side="left", padx=1)
        ttk.Button(header, text="🗑", width=3, command=self._clear_chat).pack(side="left", padx=1)

        self.status_canvas = tk.Canvas(header, width=16, height=16, highlightthickness=0)
        self.status_canvas.pack(side="left", padx=5)
        self._update_status_indicator(False)

        # ---- 输入区域（先打包，确保始终可见） ----
        input_frame = tk.Frame(self, padx=5, pady=5)
        input_frame.pack(side="bottom", fill="x")

        # 快捷按钮行
        quick_row = tk.Frame(input_frame)
        quick_row.pack(fill="x", pady=(0, 3))
        ttk.Button(quick_row, text="📋 插入选中SQL", command=self._insert_selected_sql).pack(side="left", padx=2)
        ttk.Button(quick_row, text="🧹 清空上下文", command=self._clear_context).pack(side="left", padx=2)

        # 输入框 + 发送按钮（Canvas 圆形图标）
        input_row = tk.Frame(input_frame)
        input_row.pack(fill="x")

        # 圆形图标发送/停止按钮（先打包，确保不被挤掉）
        self._btn_size = 36
        self.send_canvas = tk.Canvas(input_row, width=self._btn_size, height=self._btn_size,
                                      highlightthickness=0, cursor="hand2",
                                      bg=input_row.cget("bg"))
        self.send_canvas.pack(side="right", padx=(4, 0), pady=2)
        self._draw_send_icon()
        self.send_canvas.bind("<Button-1>", lambda e: self._on_send_or_stop())
        self.send_canvas.bind("<Enter>", lambda e: self._on_btn_hover(True))
        self.send_canvas.bind("<Leave>", lambda e: self._on_btn_hover(False))

        self.input_text = tk.Text(input_row, height=3, wrap="word",
                                   font=("Microsoft YaHei", 10),
                                   fg="#999999")
        self.input_text.pack(side="left", fill="both", expand=True)
        self.input_text.bind("<Return>", self._on_enter_key)
        self.input_text.bind("<Shift-Return>", lambda e: None)
        self.input_text.bind("<KeyRelease>", lambda e: self._auto_resize_text(self.input_text, 3, 6))
        self._bind_blocked_keys(self.input_text)

        # 占位文本
        self._placeholder_visible = True
        self._placeholder_text = "请输入您的问题…  Enter 发送  |  Shift+Enter 换行"
        self.input_text.insert("1.0", self._placeholder_text)
        self.input_text.tag_configure("placeholder", foreground="#aaaaaa",
                                       font=("Microsoft YaHei", 10))
        self.input_text.tag_add("placeholder", "1.0", "end")
        self.input_text.bind("<FocusIn>", self._on_input_focus_in)
        self.input_text.bind("<FocusOut>", self._on_input_focus_out)

        # ---- 消息展示区（最后打包，填充剩余空间） ----
        msg_frame = tk.Frame(self)
        msg_frame.pack(side="top", fill="both", expand=True, padx=3, pady=3)

        self.msg_area = tk.Text(msg_frame, wrap="word", state="disabled",
                                 font=("Microsoft YaHei", 10), cursor="",
                                 bg="#fafafa", relief="flat", padx=8, pady=8)
        self.msg_scroll = ttk.Scrollbar(msg_frame, orient="vertical", command=self.msg_area.yview)
        self.msg_area.configure(yscrollcommand=self._on_msg_area_scroll)
        self.msg_area.pack(side="left", fill="both", expand=True)
        self.msg_scroll.pack(side="right", fill="y")

        # 消息区拦截快捷键，并绑定复制按钮事件
        self._bind_blocked_keys(self.msg_area)
        self.msg_area.tag_bind("copy_link", "<Button-1>", self._on_copy_code)
        self.msg_area.tag_bind("copy_link", "<Enter>", lambda e: self.msg_area.config(cursor="hand2"))
        self.msg_area.tag_bind("copy_link", "<Leave>", lambda e: self.msg_area.config(cursor=""))
        # 用户消息编辑：双击触发编辑
        self.msg_area.tag_bind("user_msg", "<Double-Button-1>", self._on_user_msg_double_click)
        self.msg_area.tag_bind("user_msg", "<Enter>", lambda e: self.msg_area.config(cursor="hand2"))
        self.msg_area.tag_bind("user_msg", "<Leave>", lambda e: self.msg_area.config(cursor=""))
        self.msg_area.tag_bind("edit_btn", "<Button-1>", self._on_edit_btn_click)
        self.msg_area.tag_bind("edit_btn", "<Enter>", lambda e: self.msg_area.config(cursor="hand2"))
        self.msg_area.tag_bind("edit_btn", "<Leave>", lambda e: self.msg_area.config(cursor=""))

        self._setup_msg_tags()
        self.renderer = MarkdownRenderer(self.msg_area)

        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制", command=self._copy_selection)
        self.msg_area.bind("<Button-3>", self._show_context_menu)

        # 增加中键/左键拖拽滚动和滚轮支持
        self.msg_area.bind("<Button-2>", self._on_drag_start)
        self.msg_area.bind("<B2-Motion>", self._on_drag_motion)
        self.msg_area.bind("<MouseWheel>", self._on_mousewheel)
        # Linux 滚轮支持
        self.msg_area.bind("<Button-4>", self._on_mousewheel)
        self.msg_area.bind("<Button-5>", self._on_mousewheel)

        # 回到底部按钮（浮动）
        self._scroll_bottom_btn = None
        self._is_at_bottom = True

        # 动态等待点动画
        self._loading_dots = 0
        self._loading_after_id = None

    # ---- 自动伸缩 ----

    def _auto_resize_text(self, text_widget, min_h=1, max_h=6):
        """根据内容行数自动调整 Text 高度"""
        content = text_widget.get("1.0", "end-1c")
        lines = content.count("\n") + 1
        # 也考虑实际折行（内容宽度导致的自动换行）
        # 回退方案：直接取行数
        new_h = max(min_h, min(lines, max_h))
        text_widget.configure(height=new_h)

    # ---- 输入占位处理 ----

    def _on_input_focus_in(self, event):
        """输入框获得焦点时清除占位文本"""
        if self._placeholder_visible:
            self.input_text.delete("1.0", "end")
            self.input_text.configure(fg="#333333")
            self._placeholder_visible = False

    def _on_input_focus_out(self, event):
        """输入框失去焦点时如果没有内容则恢复占位文本"""
        if not self.input_text.get("1.0", "end-1c").strip():
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", self._placeholder_text)
            self.input_text.tag_add("placeholder", "1.0", "end")
            self.input_text.configure(fg="#999999")
            self._placeholder_visible = True

    # ---- 滚动同步 ----

    def _on_msg_area_scroll(self, *args):
        """消息区滚动事件，检测是否在底部"""
        if args[0] == 'moveto':
            pos = float(args[1])
            self._is_at_bottom = (pos >= 0.99)
        self._update_scroll_bottom_btn()
        # 同步滚动条
        self.msg_scroll.set(*args)

    def _update_scroll_bottom_btn(self):
        """根据滚动位置更新'回到底部'按钮"""
        if self._is_at_bottom:
            if self._scroll_bottom_btn:
                self._scroll_bottom_btn.place_forget()
        else:
            if not self._scroll_bottom_btn:
                self._scroll_bottom_btn = tk.Label(
                    self.msg_area, text="↓ 回到底部", cursor="hand2",
                    font=("Microsoft YaHei", 9),
                    fg="#ffffff", bg="#666666",
                    padx=10, pady=3
                )
                self._scroll_bottom_btn.bind("<Button-1>", self._scroll_to_bottom)
            self._scroll_bottom_btn.place(relx=0.98, rely=0.98, anchor="se")

    def _scroll_to_bottom(self, event=None):
        """滚动到消息区底部"""
        self.msg_area.see("end")
        if self._scroll_bottom_btn:
            self._scroll_bottom_btn.place_forget()
        self._is_at_bottom = True

    def _scroll_msg_to_bottom(self):
        """如果用户在底部，自动滚动到最新消息"""
        if self._is_at_bottom:
            self.msg_area.see("end")

    def _show_context_menu(self, event):
        """显示右键菜单，仅在有非空选中内容时显示"""
        try:
            # 严格检查：必须有 sel 标记，且选中的内容去除空白后非空
            sel_ranges = self.msg_area.tag_ranges("sel")
            if sel_ranges:
                selected_text = self.msg_area.get(sel_ranges[0], sel_ranges[1]).strip()
                if selected_text:
                    self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            pass

    def _copy_selection(self):
        """复制选中的文本到剪贴板"""
        try:
            selected_text = self.msg_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected_text:
                self.clipboard_clear()
                self.clipboard_append(selected_text)
        except tk.TclError:
            pass  # 没有选中内容时忽略错误

    def _on_copy_code(self, event):
        """点击 [复制] 按钮时，提取下方代码块内容并复制"""
        # 获取点击位置的索引
        index = self.msg_area.index(f"@{event.x},{event.y}")
        # 查找紧随其后的 code_block tag 范围
        search_start = self.msg_area.index(f"{index} lineend + 1c")
        # 寻找下一个 code_block tag
        ranges = self.msg_area.tag_nextrange("code_block", search_start)
        if ranges:
            code_text = self.msg_area.get(ranges[0], ranges[1]).strip()
            self.clipboard_clear()
            self.clipboard_append(code_text)
            messagebox.showinfo("成功", "代码已复制到剪贴板", parent=self)

    # ---- 拖拽滚动支持 ----

    def _on_drag_start(self, event):
        """记录拖拽开始位置"""
        self.msg_area.scan_mark(event.x, event.y)

    def _on_drag_motion(self, event):
        """执行拖拽滚动"""
        self.msg_area.scan_dragto(event.x, event.y, gain=1)

    def _on_mousewheel(self, event):
        """处理鼠标滚轮"""
        if event.num == 4:  # Linux scroll up
            self.msg_area.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.msg_area.yview_scroll(1, "units")
        else:  # Windows/MacOS
            self.msg_area.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    # ---- 圆形图标按钮绘制 ----

    def _draw_send_icon(self):
        """绘制发送图标（白色向上箭头，深色圆形背景）"""
        c = self.send_canvas
        c.delete("all")
        s = self._btn_size
        r = s // 2 - 2
        cx, cy = s // 2, s // 2

        # 圆形背景
        bg = self._send_btn_hover_bg if hasattr(self, '_send_btn_hover_bg') else "#1a73e8"
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=bg, outline="")

        # 向上箭头（发送）
        # 箭头杆
        c.create_line(cx, cy + 7, cx, cy - 5, fill="white", width=2.5, capstyle="round")
        # 箭头两翼
        c.create_line(cx - 5, cy, cx, cy - 5, fill="white", width=2.5, capstyle="round")
        c.create_line(cx + 5, cy, cx, cy - 5, fill="white", width=2.5, capstyle="round")

    def _draw_stop_icon(self):
        """绘制停止图标（白色方块，红色圆形背景）"""
        c = self.send_canvas
        c.delete("all")
        s = self._btn_size
        r = s // 2 - 2
        cx, cy = s // 2, s // 2

        # 圆形背景
        bg = self._send_btn_hover_bg if hasattr(self, '_send_btn_hover_bg') else "#e53935"
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=bg, outline="")

        # 方块
        half = 5
        c.create_rectangle(cx - half, cy - half, cx + half, cy + half, fill="white", outline="")

    def _on_btn_hover(self, entering):
        """鼠标悬停时微调背景色"""
        if self.is_streaming:
            self._send_btn_hover_bg = "#ef5350" if entering else "#e53935"
            self._draw_stop_icon()
        else:
            self._send_btn_hover_bg = "#4285f4" if entering else "#1a73e8"
            self._draw_send_icon()

    def _update_send_btn_state(self):
        """根据流式状态切换图标"""
        if self.is_streaming:
            self._send_btn_hover_bg = "#e53935"
            self._draw_stop_icon()
        else:
            self._send_btn_hover_bg = "#1a73e8"
            self._draw_send_icon()

    def _bind_blocked_keys(self, widget):
        """为组件绑定快捷键拦截，阻止冒泡到 SQL 工作台"""
        for key in self._BLOCKED_KEYS:
            widget.bind(key, lambda e: "break")

    @staticmethod
    def _lighten(hex_color, amount=20):
        """使颜色变亮（用于暗色主题的 hover/背景）"""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            r = min(255, r + amount)
            g = min(255, g + amount)
            b = min(255, b + amount)
            return f'#{r:02x}{g:02x}{b:02x}'
        except: return hex_color

    @staticmethod
    def _dim(hex_color, factor=50):
        """使颜色变暗/变浅（factor 越小越暗），用于辅助文字"""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            factor = max(0, min(100, factor)) / 100.0
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            return f'#{r:02x}{g:02x}{b:02x}'
        except: return hex_color

    def _setup_msg_tags(self):
        """配置消息区域的样式 tag（基于统一主题）"""
        c = getattr(self, '_colors', None) or get_theme_colors('默认')
        dark = getattr(self, '_is_dark', False)
        bg, fg = c["bg"], c["fg"]
        accent = c["accent"]
        hb = c["hb"]

        # 暗色辅助色
        user_bg = c.get("select_bg", "#e3f2fd") if not dark else self._lighten(bg, 15)
        ai_bg = hb if dark else "#f5f5f5"
        user_lbl = accent
        user_tm = self._dim(accent, 60) if dark else "#90caf9"
        ai_lbl = accent if dark else "#666666"
        ai_tm = self._dim(fg, 50) if dark else "#cccccc"

        self.msg_area.tag_configure('user_msg', background=user_bg, lmargin1=10, lmargin2=10,
                                     spacing1=5, spacing3=5, relief='flat')
        self.msg_area.tag_configure('user_label', foreground=user_lbl,
                                     font=('Microsoft YaHei', 8, 'bold'),
                                     lmargin1=10, lmargin2=10)
        self.msg_area.tag_configure('user_time', foreground=user_tm,
                                     font=('Microsoft YaHei', 7),
                                     lmargin1=10, lmargin2=10)
        self.msg_area.tag_configure('ai_msg', background=ai_bg, lmargin1=10, lmargin2=10,
                                     spacing1=5, spacing3=5, relief='flat')
        self.msg_area.tag_configure('ai_label', foreground=ai_lbl,
                                     font=('Microsoft YaHei', 8, 'bold'),
                                     lmargin1=10, lmargin2=10)
        self.msg_area.tag_configure('ai_time', foreground=ai_tm,
                                     font=('Microsoft YaHei', 7),
                                     lmargin1=10, lmargin2=10)
        sys_fg = self._dim(fg, 40) if dark else "#999999"
        self.msg_area.tag_configure('system_msg', foreground=sys_fg,
                                     font=('Microsoft YaHei', 9), justify='center')
        err_fg = c.get("danger", "#cc0000")
        self.msg_area.tag_configure('error_msg', foreground=err_fg,
                                     font=('Microsoft YaHei', 9),
                                     lmargin1=10, lmargin2=10)
        err_lbl = err_fg if dark else "#e53935"
        self.msg_area.tag_configure('error_label', foreground=err_lbl,
                                     font=('Microsoft YaHei', 8, 'bold'),
                                     lmargin1=10, lmargin2=10)
        warn_fg = "#e65100"
        self.msg_area.tag_configure('warning_msg', foreground=warn_fg,
                                     font=('Microsoft YaHei', 9),
                                     lmargin1=10, lmargin2=10)
        self.msg_area.tag_configure('retry_btn', foreground=accent,
                                     font=('Microsoft YaHei', 9, 'underline'),
                                     lmargin1=10, lmargin2=10)
        edit_fg = self._dim(accent, 50) if dark else "#90caf9"
        self.msg_area.tag_configure('edit_btn', foreground=edit_fg,
                                     font=('Microsoft YaHei', 8),
                                     lmargin1=10, lmargin2=10, spacing3=8)
        stream_fg = fg if dark else "#333333"
        self.msg_area.tag_configure('streaming', foreground=stream_fg,
                                     font=('Microsoft YaHei', 10))
        copy_fg = self._dim(fg, 50) if dark else "#888888"
        self.msg_area.tag_configure('copy_button', foreground=copy_fg,
                                     font=('Consolas', 8), justify='right')
        title_fg = fg if dark else "#333333"
        self.msg_area.tag_configure('welcome_title', foreground=title_fg,
                                     font=('Microsoft YaHei', 14, 'bold'),
                                     justify='center', spacing1=20, spacing3=5)
        sub_fg = self._dim(fg, 40) if dark else "#999999"
        self.msg_area.tag_configure('welcome_subtitle', foreground=sub_fg,
                                     font=('Microsoft YaHei', 10),
                                     justify='center', spacing1=2, spacing3=2)
        tip_fg = self._dim(fg, 35) if dark else "#bbbbbb"
        self.msg_area.tag_configure('welcome_tip', foreground=tip_fg,
                                     font=('Microsoft YaHei', 9),
                                     justify='center', spacing1=2, spacing3=20)

    def _update_status_indicator(self, has_context):
        """更新状态指示灯（静态圆点）"""
        c = getattr(self, '_colors', None) or get_theme_colors('默认')
        accent = c["accent"]
        dark = getattr(self, '_is_dark', False)
        inactive = self._dim(c["fg"], 50) if dark else "#bdbdbd"
        self.status_canvas.delete("all")
        color = accent if has_context else inactive
        self.status_canvas.create_oval(3, 3, 13, 13, fill=color, outline="")

    def _start_spinner(self):
        """开始转圈动画"""
        self._spinner_angle = 0
        self._animate_spinner()

    def _stop_spinner(self):
        """停止转圈动画"""
        if self._spinner_after_id:
            self.after_cancel(self._spinner_after_id)
            self._spinner_after_id = None
        # 恢复为状态指示灯
        self._update_status_indicator(bool(self.table_context))

    def _animate_spinner(self):
        """转圈动画帧"""
        c = getattr(self, '_colors', None) or get_theme_colors('默认')
        accent = c["accent"]
        dark = getattr(self, '_is_dark', False)
        outline_inactive = self._dim(c["fg"], 50) if dark else "#e0e0e0"

        self.status_canvas.delete("all")
        cx, cy, r = 8, 8, 6
        # 画灰色背景圆
        self.status_canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                       outline=outline_inactive, width=2)
        # 画旋转弧线
        start = self._spinner_angle
        self.status_canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                      start=start, extent=90,
                                      style="arc", outline=accent, width=2)
        self._spinner_angle = (self._spinner_angle + 30) % 360
        self._spinner_after_id = self.after(60, self._animate_spinner)

    def _start_loading_animation(self):
        """开始等待点动画"""
        self._loading_dots = 1
        self._animate_loading()

    def _stop_loading_animation(self):
        """停止等待点动画"""
        if self._loading_after_id:
            self.after_cancel(self._loading_after_id)
            self._loading_after_id = None

    def _animate_loading(self):
        """等待点动画帧"""
        if not self.is_streaming or self._current_assistant_text:
            return
            
        dots = "." * self._loading_dots
        self.msg_area.configure(state="normal")
        self.msg_area.delete(self._stream_start_pos, "end-1c")
        self.msg_area.insert(self._stream_start_pos, dots, "ai_msg")
        self.msg_area.configure(state="disabled")
        
        self._loading_dots = (self._loading_dots % 3) + 1
        self._loading_after_id = self.after(500, self._animate_loading)

    # ---- 配置管理 ----

    def _load_configs(self):
        """加载 AI 配置列表"""
        self._ai_configs = self.storage.get_ai_configs()
        names = [c['name'] + (" ★" if c.get('is_default') else "") for c in self._ai_configs]
        self.config_combo['values'] = names

        default_cfg = self.storage.get_default_ai_config()
        if default_cfg:
            self._active_config = default_cfg
            for i, c in enumerate(self._ai_configs):
                if c['id'] == default_cfg['id']:
                    self.config_combo.current(i)
                    break
        elif self._ai_configs:
            self.config_combo.current(0)
            self._active_config = self._ai_configs[0]

    def _on_config_changed(self, event=None):
        """切换 AI 配置"""
        idx = self.config_combo.current()
        if 0 <= idx < len(self._ai_configs):
            self._active_config = self._ai_configs[idx]

    def _get_active_config(self):
        """获取当前激活性 AI 配置"""
        idx = self.config_combo.current()
        if 0 <= idx < len(self._ai_configs):
            return self._ai_configs[idx]
        cfg = self.storage.get_default_ai_config()
        if cfg:
            return cfg
        return None

    # ---- 会话管理 ----

    def _open_session_wizard(self):
        """打开初始化会话向导"""
        SessionWizard(self, conn_data=self.conn_data, db_name=self.db_name,
                      schema_name=self.schema_name, db_ops=self.db_ops,
                      on_complete=self._on_session_initialized)

    def _on_session_initialized(self, context_text, conn_id, database, schema, selected_tables):
        """会话初始化完成回调"""
        self.table_context = context_text
        self.table_context_summary = f"{database}.{schema or ''} 的 {len(selected_tables)} 个表"
        self._update_status_indicator(True)
        
        # 将初始化信息作为系统消息加入历史，以便持久化
        init_msg = f"已加载 {self.table_context_summary} 的结构，AI 将基于这些信息进行回答"
        self.messages = [{
            'role': 'system',
            'content': init_msg,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }]
        
        self._refresh_msg_area()
        self._save_history()

    def _clear_chat(self):
        """清空对话"""
        if not messagebox.askyesno("确认", "确定要清空当前对话吗？", parent=self):
            return
        self.messages = []
        # 如果有上下文，保留一个系统提示
        if self.table_context:
            self.messages.append({
                'role': 'system',
                'content': f"已加载 {self.table_context_summary} 的结构（对话已清空）",
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
        self._refresh_msg_area()
        self._save_history()

    def _clear_context(self):
        """清空表结构上下文"""
        if not self.table_context:
            messagebox.showinfo("提示", "当前没有加载任何表结构上下文", parent=self.winfo_toplevel())
            return
        if not messagebox.askyesno("确认", "确定要清空表结构上下文吗？\n清空后 AI 将不再参考表结构信息。", parent=self.winfo_toplevel()):
            return
        self.table_context = ''
        self.table_context_summary = ''
        self._update_status_indicator(False)
        self.messages.append({
            'role': 'system',
            'content': "已清空表结构上下文",
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        self._refresh_msg_area()
        self._save_history()

    def _insert_selected_sql(self):
        """插入当前 SQL 编辑器中选中的文本"""
        workbench = self._get_workbench()
        if workbench and hasattr(workbench, 'editor'):
            try:
                selected = workbench.editor.get("sel.first", "sel.last")
                if selected.strip():
                    self.input_text.insert("end", selected)
                    return
            except tk.TclError:
                pass
        messagebox.showinfo("提示", "请先在 SQL 编辑器中选中一段文本", parent=self)

    def _get_workbench(self):
        """获取所属的 SQLWorkbench 实例"""
        widget = self.master
        while widget:
            if widget.__class__.__name__ == 'SQLWorkbench':
                return widget
            widget = widget.master
        return None

    # ---- 消息发送与接收 ----

    def _on_enter_key(self, event):
        """Enter 发送消息，Shift+Enter 换行"""
        if event.state & 0x1:  # Shift 键
            return None  # 允许默认换行
        self._on_send_or_stop()
        return "break"  # 阻止默认换行

    def _on_send_or_stop(self):
        """发送/停止按钮"""
        if self.is_streaming:
            self._stop_streaming()
        else:
            self._send_message()

    def _stop_streaming(self):
        """停止当前流式响应，立即完成"""
        if not self.is_streaming:
            return
        # 清空队列中残留的 chunk，防止后续处理
        try:
            while not self.chunk_queue.empty():
                self.chunk_queue.get_nowait()
        except queue.Empty:
            pass
        # 立即用当前已接收的文本完成消息
        text = self._current_assistant_text
        if text:
            text += "\n\n[已停止]"
        else:
            text = "[已停止]"
        self._finalize_message(text)

    def _send_message(self):
        """发送消息"""
        if self.is_streaming:
            return

        text = self.input_text.get("1.0", "end-1c").strip()
        if not text:
            return

        config = self._get_active_config()
        if not config:
            messagebox.showwarning("提示", "请先配置 AI 设置\n（文件 → AI 设置）", parent=self)
            return

        if not config.get('api_key'):
            messagebox.showwarning("提示", "当前 AI 配置缺少 API Key\n请先在 AI 设置中配置", parent=self)
            return

        # 添加用户消息
        self.messages.append({
            'role': 'user',
            'content': text,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        self._append_user_message(text)
        self.input_text.delete("1.0", "end")

        # 准备发送给 AI 的消息列表
        api_messages = self._build_api_messages()

        # 开始流式请求
        self.is_streaming = True
        self._stop_requested = False
        self._update_send_btn_state()
        self._start_spinner()
        self._current_assistant_text = ''
        self._append_ai_placeholder()
        self._start_loading_animation()

        def stream_worker():
            try:
                client = AIClient(config)
                client.chat_completion_async(api_messages, self.chunk_queue, stream=True)
            except Exception as e:
                self.chunk_queue.put(('error', str(e)))

        threading.Thread(target=stream_worker, daemon=True).start()
        self.after(50, self._poll_chunks)

    def _build_api_messages(self):
        """构建发送给 AI API 的消息列表"""
        api_msgs = []
        system_parts = []
        config = self._get_active_config()
        if config and config.get('system_prompt'):
            system_parts.append(config['system_prompt'])
        if self.table_context:
            system_parts.append("你是一个专业的数据库助手，可以帮用户编写 SQL、解释表结构、优化查询等。")
            system_parts.append(self.table_context)
        if system_parts:
            api_msgs.append({'role': 'system', 'content': '\n\n'.join(system_parts)})

        for msg in self.messages:
            api_msgs.append({'role': msg['role'], 'content': msg['content']})
        return api_msgs

    def _poll_chunks(self):
        """轮询流式响应 chunk"""
        while True:
            try:
                event_type, data = self.chunk_queue.get_nowait()
                if event_type == 'chunk':
                    self._stop_loading_animation()
                    self._current_assistant_text += data
                    self._update_streaming_text(self._current_assistant_text)
                elif event_type == 'done':
                    self._stop_loading_animation()
                    if self._stop_requested:
                        self._finalize_message(self._current_assistant_text + "\n\n[已停止]")
                    else:
                        self._finalize_message(self._current_assistant_text)
                    return
                elif event_type == 'error':
                    self._stop_loading_animation()
                    self._finalize_message_with_error(data)
                    return
            except queue.Empty:
                break

        if self.is_streaming:
            self.after(50, self._poll_chunks)

    def _append_user_message(self, text):
        """追加用户消息到展示区（含时间戳）"""
        now = datetime.now().strftime('%H:%M:%S')
        msg_index = len(self.messages) - 1
        self.msg_area.configure(state="normal")
        self._render_user_message(text, now, msg_index=msg_index)
        self.msg_area.configure(state="disabled")
        self._scroll_msg_to_bottom()

    def _append_ai_placeholder(self):
        """追加 AI 消息占位（含时间戳）"""
        now = datetime.now().strftime('%H:%M:%S')
        self.msg_area.configure(state="normal")
        self.msg_area.insert("end", "\n")
        self.msg_area.insert("end", "🤖 AI  ", "ai_label")
        self.msg_area.insert("end", now + "\n", "ai_time")
        self._stream_start_pos = self.msg_area.index("end-1c")
        self.msg_area.insert("end", "...\n", "ai_msg")
        self.msg_area.configure(state="disabled")
        self._scroll_msg_to_bottom()

    def _update_streaming_text(self, text):
        """更新流式文本"""
        self.msg_area.configure(state="normal")
        self.msg_area.delete(self._stream_start_pos, "end-1c")
        self.msg_area.insert(self._stream_start_pos, text, "streaming")
        self.msg_area.configure(state="disabled")
        self._scroll_msg_to_bottom()

    def _finalize_message(self, text):
        """完成 AI 消息（流式结束后 Markdown 渲染）"""
        self.is_streaming = False
        self._update_send_btn_state()
        self._stop_spinner()
        self._stop_loading_animation()

        timestamp = datetime.now().strftime('%H:%M:%S')
        self.messages.append({
            'role': 'assistant',
            'content': text,
            'timestamp': timestamp
        })

        # 删除流式占位内容，用完整 Markdown 渲染替换
        self.msg_area.configure(state="normal")
        self.msg_area.delete(self._stream_start_pos, "end-1c")
        self.renderer.render(text)
        self.msg_area.configure(state="disabled")
        self._scroll_msg_to_bottom()
        self._save_history()

    def _finalize_message_with_error(self, error):
        """AI 消息出错，显示错误及重试按钮"""
        self.is_streaming = False
        self._update_send_btn_state()
        self._stop_spinner()
        self._stop_loading_animation()

        # 保存失败前的最后一条用户消息以供重试
        self._last_failed_content = None
        if self.messages and self.messages[-1].get('role') == 'user':
            self._last_failed_content = self.messages[-1].get('content', '')

        self.msg_area.configure(state="normal")
        self.msg_area.delete(self._stream_start_pos, "end-1c")
        self.msg_area.insert("end", "⚠ 请求失败\n", "error_label")
        self.msg_area.insert("end", f"{error}\n", "error_msg")
        if self._last_failed_content:
            self.msg_area.insert("end", "点击重试 ⟳  ", "retry_btn")
            self.msg_area.tag_bind("retry_btn", "<Button-1>", self._on_retry_click)
            self.msg_area.tag_bind("retry_btn", "<Enter>", lambda e: self.msg_area.config(cursor="hand2"))
            self.msg_area.tag_bind("retry_btn", "<Leave>", lambda e: self.msg_area.config(cursor=""))
        self.msg_area.configure(state="disabled")
        self._scroll_msg_to_bottom()

    def _on_retry_click(self, event=None):
        """点击重试按钮，重新发送上一条消息"""
        if self._last_failed_content:
            content = self._last_failed_content
            self._last_failed_content = None
            # 移除上次失败前添加的用户消息，避免重试时重复
            if self.messages and self.messages[-1].get('role') == 'user':
                self.messages.pop()
            # 回填输入框并发送
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", content)
            self._on_input_focus_in(None)
            self._send_message()

    def _append_system_message(self, text):
        """追加系统消息"""
        self.msg_area.configure(state="normal")
        self.msg_area.insert("end", f"— {text} —\n", "system_msg")
        self.msg_area.configure(state="disabled")
        self.msg_area.see("end")

    def _refresh_msg_area(self):
        """重新渲染所有消息"""
        self.msg_area.configure(state="normal")
        self.msg_area.delete("1.0", "end")
        self._user_msg_ranges.clear()

        if not self.messages:
            self._show_welcome()
        else:
            for i, msg in enumerate(self.messages):
                role = msg.get('role', '')
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', '')

                if role == 'user':
                    self._render_user_message(content, timestamp, msg_index=i)
                elif role == 'assistant':
                    self._render_assistant_message(content, timestamp)
                elif role == 'system':
                    self.msg_area.insert("end", f"— {content} —\n", "system_msg")

        self.msg_area.configure(state="disabled")
        self._scroll_msg_to_bottom()

    def _show_welcome(self):
        """显示欢迎页"""
        self.msg_area.insert("end", "\n\n\n")
        self.msg_area.insert("end", "MDBS AI 助手\n", "welcome_title")
        self.msg_area.insert("end", "基于 OpenAI 协议的智能数据库助手\n", "welcome_subtitle")
        self.msg_area.insert("end", "\n")
        self.msg_area.insert("end", "支持：编写 SQL · 解释表结构 · 查询优化 · 数据诊断\n", "welcome_subtitle")
        self.msg_area.insert("end", "\n")
        self.msg_area.insert("end", "点击 ⚙ 加载表结构上下文，或直接开始提问\n", "welcome_tip")

    def _render_user_message(self, content, timestamp, msg_index=None):
        """渲染用户消息气泡（含时间戳）"""
        self.msg_area.insert("end", "\n")
        self.msg_area.insert("end", "🧑 你  ", "user_label")
        if timestamp:
            self.msg_area.insert("end", timestamp + "\n", "user_time")
        else:
            self.msg_area.insert("end", "\n", "user_time")
        start = self.msg_area.index("end-1c")
        self.msg_area.insert("end", content, "user_msg")
        self.msg_area.insert("end", " ✎\n", "edit_btn")
        if msg_index is not None:
            end = self.msg_area.index("end-1c")
            self._user_msg_ranges.append((start, end, msg_index))

    def _render_assistant_message(self, content, timestamp):
        """渲染 AI 消息气泡（含时间戳）"""
        self.msg_area.insert("end", "\n")
        self.msg_area.insert("end", "🤖 AI  ", "ai_label")
        if timestamp:
            self.msg_area.insert("end", timestamp + "\n", "ai_time")
        else:
            self.msg_area.insert("end", "\n", "ai_time")
        self.renderer.render(content)

    # ---- 消息编辑与重新生成 ----

    def _on_edit_btn_click(self, event):
        """点击用户消息末尾的 ✎ 编辑按钮"""
        click_idx = self.msg_area.index(f"@{event.x},{event.y}")
        for start, end, msg_idx in self._user_msg_ranges:
            if (self.msg_area.compare(start, "<=", click_idx)
                    and self.msg_area.compare(click_idx, "<=", end)):
                self._edit_user_message(msg_idx)
                break

    def _on_user_msg_double_click(self, event):
        """双击用户消息，打开编辑对话框"""
        click_idx = self.msg_area.index(f"@{event.x},{event.y}")
        for start, end, msg_idx in self._user_msg_ranges:
            if (self.msg_area.compare(start, "<=", click_idx)
                    and self.msg_area.compare(click_idx, "<=", end)):
                self._edit_user_message(msg_idx)
                break

    def _edit_user_message(self, msg_index):
        """编辑指定索引的用户消息 — 内联编辑区域（点击修改，确认/取消生效）"""
        if self.is_streaming:
            return
        original = self.messages[msg_index].get('content', '')

        # 后续消息数量（用于提示用户）
        remaining = len(self.messages) - msg_index - 1

        # 查找消息在 msg_area 中的索引范围
        for start, end, idx in self._user_msg_ranges:
            if idx != msg_index:
                continue

            # 获取主题颜色
            colors = getattr(self, '_colors', get_theme_colors(
                self.settings.get('theme', '默认')))
            bg, fg = colors["bg"], colors["fg"]
            hb = colors["hb"]
            accent = colors["accent"]
            is_dark = getattr(self, '_is_dark', is_dark_theme(
                self.settings.get('theme', '默认')))

            # 保存稳定的位置标记
            msg_start = self.msg_area.index(start)
            msg_end = self.msg_area.index(end)

            # 计算合适的高度
            # 内联编辑框架（DeepSeek 简洁风格）
            edit_frame = tk.Frame(self.msg_area, bg=bg, padx=0, pady=0)

            # 文本编辑器（flat 风格，accent 细边框）
            edit_text = tk.Text(edit_frame, wrap="word",
                                font=(self.settings.get('font_family', 'Microsoft YaHei'),
                                      self.settings.get('font_size_content', 10)),
                                height=1, undo=True,
                                relief="flat",
                                highlightthickness=1,
                                highlightbackground=accent,
                                highlightcolor=accent,
                                bg=hb if is_dark else "#ffffff", fg=fg,
                                insertbackground=fg,
                                padx=6, pady=6)
            edit_text.pack(fill="both", expand=True)
            edit_text.insert("1.0", original)
            edit_text.focus_set()
            edit_text.tag_add("sel", "1.0", "end-1c")
            # 根据内容调整初始高度
            content_lines = original.count("\n") + 1
            edit_text.configure(height=max(1, min(content_lines, 8)))
            edit_text.bind("<KeyRelease>", lambda e: self._auto_resize_text(edit_text, 1, 8))

            # ---- 底部栏（提示 + 按钮） ----
            bottom_bar = tk.Frame(edit_frame, bg=bg)
            bottom_bar.pack(fill="x", pady=(3, 0))

            # 左侧：小幅提示
            hint_parts = ["修改后将重新生成回复"]
            if remaining > 0:
                hint_parts.append(f"（丢弃 {remaining} 条）")
            tk.Label(bottom_bar, text="".join(hint_parts),
                     font=("Microsoft YaHei", 7),
                     fg="#888888", bg=bg,
                     anchor="w").pack(side="left", fill="x", expand=True)

            # 右侧：按钮组
            btn_frame = tk.Frame(bottom_bar, bg=bg)
            btn_frame.pack(side="right")

            cancel_btn = tk.Label(btn_frame, text="取消", cursor="hand2",
                                  font=("Microsoft YaHei", 9),
                                  fg=fg, bg=bg, padx=8, pady=1)
            cancel_btn.pack(side="right", padx=(2, 0))

            confirm_btn = tk.Label(btn_frame, text="✓ 确认", cursor="hand2",
                                   font=("Microsoft YaHei", 9),
                                   fg=accent, bg=bg, padx=8, pady=1)
            confirm_btn.pack(side="right", padx=(2, 0))

            # ---- 操作回调 ----
            def do_confirm(t=edit_text, mi=msg_index):
                new_content = t.get("1.0", "end-1c").strip()
                if not new_content:
                    return
                self._regenerate_from(mi, new_content)

            def do_cancel(ef=edit_frame, st=msg_start, orig=original, mi=msg_index):
                ef.destroy()
                self.msg_area.configure(state="normal")
                self.msg_area.insert(st, orig + " ✎\n")
                self.msg_area.configure(state="disabled")
                new_end = self.msg_area.index(f"{st} + {len(orig) + 3} chars")
                for i, (s, e, idx) in enumerate(self._user_msg_ranges):
                    if idx == mi:
                        self._user_msg_ranges[i] = (s, new_end, idx)
                        break

            cancel_btn.bind("<Button-1>", lambda e: do_cancel())
            confirm_btn.bind("<Button-1>", lambda e: do_confirm())

            # 悬停效果
            cancel_btn.bind("<Enter>", lambda e: cancel_btn.configure(fg=accent))
            cancel_btn.bind("<Leave>", lambda e: cancel_btn.configure(fg=fg))
            confirm_btn.bind("<Enter>", lambda e: confirm_btn.configure(fg="white", bg=accent))
            confirm_btn.bind("<Leave>", lambda e: confirm_btn.configure(fg=accent, bg=bg))

            # 键盘快捷键
            def on_key(event, t=edit_text):
                if event.state & 0x4:  # Ctrl+Enter
                    if event.keysym in ('Return', 'KP_Enter'):
                        do_confirm()
                        return "break"
                if event.keysym == 'Escape':
                    do_cancel()
                    return "break"
                return None
            edit_text.bind("<Key>", on_key)

            # ---- 嵌入到消息区（撑满宽度） ----
            self.msg_area.configure(state="normal")
            self.msg_area.delete(msg_start, msg_end)
            self.msg_area.window_create(msg_start, window=edit_frame, stretch=True)
            self.msg_area.insert("end", "\n")
            self.msg_area.configure(state="disabled")
            self.msg_area.after_idle(lambda: self.msg_area.see(msg_start))
            break

    def _regenerate_from(self, msg_index, new_content):
        """从指定位置截断对话，使用新内容重新发送"""
        # 截断消息列表到该位置（不含该消息）
        self.messages = self.messages[:msg_index]
        # 添加编辑后的消息
        self.messages.append({
            'role': 'user',
            'content': new_content,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        # 重新渲染消息区
        self._refresh_msg_area()

        # 发送新消息
        config = self._get_active_config()
        if not config or not config.get('api_key'):
            return

        api_messages = self._build_api_messages()
        self.is_streaming = True
        self._stop_requested = False
        self._update_send_btn_state()
        self._start_spinner()
        self._current_assistant_text = ''
        self._append_ai_placeholder()
        self._start_loading_animation()

        def stream_worker():
            try:
                client = AIClient(config)
                client.chat_completion_async(api_messages, self.chunk_queue, stream=True)
            except Exception as e:
                self.chunk_queue.put(('error', str(e)))

        threading.Thread(target=stream_worker, daemon=True).start()
        self.after(50, self._poll_chunks)

    # ---- 对话持久化 ----

    def _save_history(self):
        """保存对话历史到 SQLite"""
        if not self.conn_id or not self.db_name:
            return
        try:
            self.storage.save_chat_history(
                self.conn_id, self.db_name, self.script_path,
                self.messages, self.table_context_summary, self.table_context
            )
        except Exception:
            pass

    def _load_history(self):
        """从 SQLite 加载对话历史"""
        if not self.conn_id or not self.db_name:
            return
        try:
            messages, context_summary, context_text = self.storage.get_chat_history(
                self.conn_id, self.db_name, self.script_path
            )
            # 只要有消息或者有上下文，就进行加载
            if messages or context_text:
                self.messages = messages
                self.table_context_summary = context_summary
                self.table_context = context_text
                if context_summary:
                    self._update_status_indicator(True)
                self._refresh_msg_area()
        except Exception:
            pass

    def save_on_close(self):
        """关闭时保存对话"""
        if self.messages or self.table_context:
            self._save_history()
