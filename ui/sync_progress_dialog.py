import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import queue
import os

class SyncProgressDialog(tk.Toplevel):
    def __init__(self, parent, cancel_event):
        super().__init__(parent)
        self.title("数据库同步中")
        self.minsize(400, 300)
        self.resizable(True, True)

        # 居中
        width, height = 600, 450
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        
        self.cancel_event = cancel_event
        self.queue = queue.Queue()
        self.is_done = False
        
        self._init_ui()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.transient(parent)
        self.grab_set()
        
        # 开始轮询队列
        self._poll_queue()

    def _init_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # 进度信息
        self.label_status = ttk.Label(main_frame, text="正在准备同步任务...", font=("Microsoft YaHei", 10, "bold"))
        self.label_status.pack(fill="x", pady=(0, 10))
        
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=5)
        
        self.label_progress = ttk.Label(main_frame, text="进度: 0/0 (0%)")
        self.label_progress.pack(fill="x", pady=(0, 10))
        
        # 日志区域
        ttk.Label(main_frame, text="详细日志:").pack(fill="x")
        self.log_area = scrolledtext.ScrolledText(main_frame, height=15, state="disabled", font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True, pady=5)
        
        # 配置日志颜色
        self.log_area.tag_config("INFO", foreground="black")
        self.log_area.tag_config("ERROR", foreground="red")
        self.log_area.tag_config("WARNING", foreground="orange")
        self.log_area.tag_config("DEBUG", foreground="gray")
        
        # 底部按钮
        self.btn_frame = ttk.Frame(main_frame)
        self.btn_frame.pack(fill="x", pady=(10, 0))
        
        self.btn_cancel = ttk.Button(self.btn_frame, text="取消任务", command=self._on_cancel)
        self.btn_cancel.pack(side="right")
        
        self.btn_close = ttk.Button(self.btn_frame, text="关闭窗口", command=self.destroy, state="disabled")
        self.btn_close.pack(side="right", padx=5)
        
        self.btn_log = ttk.Button(self.btn_frame, text="查看完整日志", command=self._open_log, state="disabled")
        self.btn_log.pack(side="left")

    def _poll_queue(self):
        try:
            while True:
                event_type, data = self.queue.get_nowait()
                if event_type == "log":
                    self._append_log(data['message'], data['level'])
                elif event_type == "progress":
                    self._update_progress(data)
                elif event_type == "done":
                    self._on_done(data)
        except queue.Empty:
            pass
        
        if not self.is_done:
            self.after(100, self._poll_queue)

    def _append_log(self, message, level):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, message, level)
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")

    def _update_progress(self, data):
        self.label_status.config(text=f"正在同步表: {data['table']}")
        self.progress['value'] = data['percent']
        self.label_progress.config(text=f"进度: {data['index']}/{data['total']} ({data['percent']}%)")

    def _on_done(self, data):
        self.is_done = True
        self.btn_cancel.config(state="disabled")
        self.btn_close.config(state="normal")
        self.log_path = data.get('log_path')
        if self.log_path:
            self.btn_log.config(state="normal")
            
        if data['status'] == "success":
            self.label_status.config(text="同步任务已成功完成！", foreground="green")
        elif data['status'] == "partial":
            self.label_status.config(text="同步任务部分成功，请检查日志", foreground="orange")
        else:
            self.label_status.config(text="同步任务失败！", foreground="red")
            if 'error' in data:
                self._append_log(f"错误原因: {data['error']}\n", "ERROR")

    def _on_cancel(self):
        if messagebox.askyesno("确认", "确定要取消正在进行的同步任务吗？"):
            self.cancel_event.set()
            self._append_log("正在请求取消任务...\n", "WARNING")

    def _on_closing(self):
        if not self.is_done:
            self._on_cancel()
        else:
            self.destroy()

    def _open_log(self):
        if hasattr(self, 'log_path') and os.path.exists(self.log_path):
            os.startfile(self.log_path)
