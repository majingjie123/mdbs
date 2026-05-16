import tkinter as tk
from tkinter import ttk


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title="请稍候", message="正在处理中..."):
        super().__init__(parent)
        self.title(title)

        # 固定宽度，高度自适应内容
        width = 300
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # 禁用关闭按钮

        self.label = ttk.Label(self, text=message, padding=10, wraplength=260)
        self.label.pack()

        self.progress = ttk.Progressbar(
            self, orient="horizontal", length=250, mode="indeterminate"
        )
        self.progress.pack(pady=10)
        self.progress.start(10)

        # 等待布局计算完成后自适应高度
        self.update_idletasks()
        label_height = self.label.winfo_reqheight()
        progress_height = self.progress.winfo_reqheight()
        height = label_height + progress_height + 50  # 50 = padding & window chrome
        height = max(height, 100)  # 最小高度 100

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.transient(parent)
        self.grab_set()

    def update_progress(self, value, message=None):
        """更新进度条数值和消息，自动切换为 determinate 模式"""
        if self.progress["mode"] == "indeterminate":
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=100)

        self.progress["value"] = value
        if message:
            self.label.config(text=message)
        self._adjust_height()

    def set_message(self, message):
        self.label.config(text=message)
        self._adjust_height()

    def close(self):
        self.progress.stop()
        self.destroy()

    def _adjust_height(self):
        """根据当前内容重新调整窗口高度"""
        self.update_idletasks()
        label_height = self.label.winfo_reqheight()
        progress_height = self.progress.winfo_reqheight()
        height = label_height + progress_height + 50
        height = max(height, 100)
        width = 300
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")