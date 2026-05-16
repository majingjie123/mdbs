import tkinter as tk
from tkinter import ttk, messagebox
import os
from models.sync_history import SyncHistoryManager

class HistoryWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("数据同步历史记录")
        self.resizable(True, True)

        # 居中
        width, height = 1200, 550
        x = (self.winfo_screenwidth() / 2) - (width / 2)
        y = (self.winfo_screenheight() / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        
        self._init_ui()
        self._refresh_list()
        
        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # 工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill="x", pady=(0, 10))
        
        ttk.Button(toolbar, text="刷新", command=self._refresh_list).pack(side="left", padx=2)
        ttk.Button(toolbar, text="清空历史", command=self._clear_history).pack(side="left", padx=2)
        ttk.Button(toolbar, text="导出 CSV", command=self._export_csv).pack(side="left", padx=2)
        
        ttk.Label(toolbar, text=" (提示: 双击行可查看同步日志)", foreground="gray").pack(side="left", padx=10)
        
        # 表格
        columns = ("id", "start_time", "source", "target", "tables", "options", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("start_time", text="开始时间")
        self.tree.heading("source", text="源连接")
        self.tree.heading("target", text="目标连接")
        self.tree.heading("tables", text="同步表")
        self.tree.heading("options", text="同步内容")
        self.tree.heading("status", text="状态")
        
        self.tree.column("id", width=40, minwidth=40)
        self.tree.column("start_time", width=160, minwidth=120)
        self.tree.column("source", width=200, minwidth=120)
        self.tree.column("target", width=200, minwidth=120)
        self.tree.column("tables", width=280, minwidth=150)
        self.tree.column("options", width=80, minwidth=60)
        self.tree.column("status", width=80, minwidth=60)

        # 让可伸缩列在窗口拉大时自动扩展
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.tree.bind("<Double-1>", self._on_double_click)

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        records = SyncHistoryManager.get_all_records()
        for r in records:
            options = []
            if r['sync_structure']: options.append("结构")
            if r['sync_data']: options.append("数据")
            
            self.tree.insert("", "end", values=(
                r['id'],
                r['start_time'],
                f"{r['source_name']}({r['source_db']})",
                f"{r['target_name']}({r['target_db']})",
                r['tables'],
                "+".join(options),
                r['status']
            ))

    def _on_double_click(self, event):
        item_id = self.tree.selection()
        if not item_id: return
        
        record_id = self.tree.item(item_id[0])['values'][0]
        record = SyncHistoryManager.get_record_by_id(record_id)
        
        if record and record.get('log_path') and os.path.exists(record['log_path']):
            os.startfile(record['log_path'])
        else:
            messagebox.showwarning("提示", "未找到对应的日志文件")

    def _clear_history(self):
        if messagebox.askyesno("确认", "确定要清空所有同步历史记录吗？"):
            SyncHistoryManager.clear_history()
            self._refresh_list()

    def _export_csv(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            if SyncHistoryManager.export_to_csv(path):
                messagebox.showinfo("成功", f"历史记录已导出到: {path}")
            else:
                messagebox.showwarning("提示", "没有可导出的记录")
