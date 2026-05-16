import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from core.ssh_manager import SSHTunnelManager
from core.db_operations import DBOperations
from core.ui_style import NavicatStyle, apply_navicat_style, center_window
from models.db_storage import DBStorage
from ui.progress_dialog import ProgressDialog
import threading

class EditDialog(tk.Toplevel):
    def __init__(self, parent, conn_data=None):
        super().__init__(parent)
        self.parent = parent
        self.title("编辑数据库连接" if conn_data else "新增数据库连接")

        # --- Navicat 风格：居中显示 ---
        width, height = 650, 650
        self.minsize(550, 580)
        self.resizable(True, True)
        center_window(self, width, height)

        self.result = None
        self.conn_data = conn_data or {}
        self.db_ops = DBOperations()

        # 获取父窗口的主题设置，应用主题感知的 Navicat 风格
        theme_name = "默认"
        if hasattr(parent, 'settings') and isinstance(parent.settings, dict):
            theme_name = parent.settings.get('theme', '默认')
        apply_navicat_style(self, theme_name)

        self._init_ui()
        if conn_data:
            self._load_data(conn_data)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _init_ui(self):
        # 使用 Grid 布局管理整个窗口
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # 1. 中间选项卡区域 - Navicat 风格间距
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=15, pady=(15, 8))

        self.tab_general = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab_general, text="  常规设置  ")
        self._setup_general_tab()

        self.tab_ssh = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab_ssh, text="  SSH 隧道  ")
        self._setup_ssh_tab()

        # 2. 分隔线
        ttk.Separator(self, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=(0, 0))

        # 3. 底部操作栏 - Navicat 风格按钮布局
        self.btn_frame = ttk.Frame(self, padding=(15, 12, 15, 15))
        self.btn_frame.grid(row=2, column=0, sticky="ew")

        # 定义按钮栏列分布：[测试SSH] [测试连接] [弹性空间] [确定] [取消]
        self.btn_frame.columnconfigure(2, weight=1)

        # 按钮 1: 测试 SSH (左一)
        self.test_ssh_btn = ttk.Button(self.btn_frame, text="⚡ 测试SSH", command=self._test_ssh, width=12)
        self.test_ssh_btn.grid(row=0, column=0, padx=(0, 8), sticky="w")

        # 按钮 2: 测试连接 (左二)
        self.test_db_btn = ttk.Button(self.btn_frame, text="⚡ 测试连接", command=self._test_db, width=12)
        self.test_db_btn.grid(row=0, column=1, padx=(0, 8), sticky="w")

        # 按钮 3: 确定 (右二 - 主要操作，使用 Primary 风格)
        self.ok_btn = ttk.Button(self.btn_frame, text="确定", command=self._on_ok, width=10, style="Navicat.Primary.TButton")
        self.ok_btn.grid(row=0, column=3, padx=(0, 8), sticky="e")

        # 按钮 4: 取消 (右一)
        self.cancel_btn = ttk.Button(self.btn_frame, text="取消", command=self.destroy, width=10)
        self.cancel_btn.grid(row=0, column=4, padx=(0, 0), sticky="e")

    def _setup_general_tab(self):
        f = ttk.Frame(self.tab_general)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        # 数据库类型 - Navicat 风格：标签统一宽度
        ttk.Label(f, text="数据库类型:", width=NavicatStyle.LABEL_WIDTH_WIDE, anchor="e").grid(row=0, column=0, sticky="ew", padx=(0, 12), pady=8)
        self.db_type = ttk.Combobox(f, values=["MySQL", "PostgreSQL"], state="readonly", width=NavicatStyle.COMBOBOX_WIDTH)
        self.db_type.set("MySQL")
        self.db_type.grid(row=0, column=1, sticky="w", pady=8)
        self.db_type.bind("<<ComboboxSelected>>", self._on_type_change)

        labels = ["连接名称:", "数据库主机:", "端口:", "用户名:", "密码:", "数据库名:"]
        self.entries = {}

        for i, label in enumerate(labels):
            row = i + 1
            ttk.Label(f, text=label, width=NavicatStyle.LABEL_WIDTH_WIDE, anchor="e").grid(row=row, column=0, sticky="ew", padx=(0, 12), pady=8)
            entry = ttk.Entry(f)
            if "密码" in label:
                entry.configure(show="*")
            entry.grid(row=row, column=1, sticky="ew", pady=8)
            self.entries[label] = entry

        # 默认值
        self.entries["端口:"].insert(0, "3306")

    def _on_type_change(self, event=None):
        """当数据库类型改变时，更新默认端口"""
        curr_type = self.db_type.get()
        self.entries["端口:"].delete(0, tk.END)
        if curr_type == "MySQL":
            self.entries["端口:"].insert(0, "3306")
        else:
            self.entries["端口:"].insert(0, "5432")
        
    def _setup_ssh_tab(self):
        f = ttk.Frame(self.tab_ssh)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        self.ssh_enabled = tk.BooleanVar()
        ttk.Checkbutton(f, text="启用 SSH 隧道", variable=self.ssh_enabled,
                        command=self._toggle_ssh).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.ssh_widgets = []

        labels = ["SSH 主机:", "SSH 端口:", "SSH 用户名:", "认证方式:", "SSH 密码:", "私钥路径:", "私钥密码:", "本地转发端口:", "远程数据库主机:", "远程数据库端口:"]
        self.ssh_entries = {}

        for i, label in enumerate(labels):
            row = i + 1
            lbl = ttk.Label(f, text=label, width=NavicatStyle.LABEL_WIDTH_WIDE, anchor="e")
            lbl.grid(row=row, column=0, sticky="ew", padx=(0, 12), pady=6)
            self.ssh_widgets.append(lbl)

            if label == "认证方式:":
                combo = ttk.Combobox(f, values=["password", "key"], state="readonly", width=NavicatStyle.COMBOBOX_WIDTH)
                combo.set("password")
                combo.grid(row=row, column=1, sticky="w", pady=6)
                self.ssh_entries[label] = combo
                self.ssh_widgets.append(combo)
            elif label == "私钥路径:":
                entry_frame = ttk.Frame(f)
                entry_frame.grid(row=row, column=1, sticky="ew", pady=6)
                entry = ttk.Entry(entry_frame)
                entry.pack(side="left", fill="x", expand=True)
                btn = ttk.Button(entry_frame, text="浏览...", width=6, command=self._browse_key)
                btn.pack(side="right")
                self.ssh_entries[label] = entry
                self.ssh_widgets.extend([entry, btn])
            else:
                entry = ttk.Entry(f, width=35)
                if "密码" in label:
                    entry.configure(show="*")
                entry.grid(row=row, column=1, sticky="ew", pady=2)
                self.ssh_entries[label] = entry
                self.ssh_widgets.append(entry)
                
        # 默认值
        self.ssh_entries["SSH 端口:"].insert(0, "22")
        self._toggle_ssh()

    def _toggle_ssh(self):
        state = "normal" if self.ssh_enabled.get() else "disabled"
        for w in self.ssh_widgets:
            if isinstance(w, ttk.Combobox):
                w.configure(state="readonly" if self.ssh_enabled.get() else "disabled")
            else:
                w.configure(state=state)

    def _browse_key(self):
        path = filedialog.askopenfilename()
        if path:
            self.ssh_entries["私钥路径:"].delete(0, tk.END)
            self.ssh_entries["私钥路径:"].insert(0, path)

    def _load_data(self, data):
        # 1. 基础设置
        self.db_type.set(data.get('db_type', 'MySQL'))
        
        entry_mapping = {
            "连接名称:": 'name',
            "数据库主机:": 'host',
            "端口:": 'port',
            "用户名:": 'user',
            "密码:": 'password',
            "数据库名:": 'database'
        }
        for label, key in entry_mapping.items():
            self.entries[label].delete(0, tk.END)
            self.entries[label].insert(0, str(data.get(key, '')) if data.get(key) is not None else '')

        # 2. SSH 隧道设置
        # 重要：加载前必须先确保控件是启用状态，否则无法 insert/delete
        for w in self.ssh_widgets:
            if isinstance(w, ttk.Combobox):
                w.configure(state="readonly")
            else:
                w.configure(state="normal")

        self.ssh_enabled.set(bool(data.get('ssh_enabled')))
        
        ssh_mapping = {
            "SSH 主机:": 'ssh_host',
            "SSH 端口:": 'ssh_port',
            "SSH 用户名:": 'ssh_user',
            "SSH 密码:": 'ssh_password',
            "私钥路径:": 'ssh_key_path',
            "私钥密码:": 'ssh_key_phrase',
            "本地转发端口:": 'ssh_local_port',
            "远程数据库主机:": 'ssh_remote_host',
            "远程数据库端口:": 'ssh_remote_port'
        }
        for label, key in ssh_mapping.items():
            self.ssh_entries[label].delete(0, tk.END)
            val = data.get(key, '')
            self.ssh_entries[label].insert(0, str(val) if val is not None else '')
        
        self.ssh_entries["认证方式:"].set(data.get('ssh_auth_type', 'password'))
        
        # 加载完成后，根据勾选状态恢复禁用/启用
        self._toggle_ssh()

    def _collect_data(self):
        try:
            # 收集常规设置 (增加 .strip() 处理)
            data = {
                'db_type': self.db_type.get(),
                'name': self.entries["连接名称:"].get().strip(),
                'host': self.entries["数据库主机:"].get().strip(),
                'port': int(self.entries["端口:"].get().strip() or 0),
                'user': self.entries["用户名:"].get().strip(),
                'password': self.entries["密码:"].get(), # 密码通常不 strip，防止空格也是密码一部分
                'database': self.entries["数据库名:"].get().strip(),
            }
            
            # 收集 SSH 设置 (增加 .strip() 处理)
            data.update({
                'ssh_enabled': 1 if self.ssh_enabled.get() else 0,
                'ssh_host': self.ssh_entries["SSH 主机:"].get().strip(),
                'ssh_port': int(self.ssh_entries["SSH 端口:"].get().strip() or 22),
                'ssh_user': self.ssh_entries["SSH 用户名:"].get().strip(),
                'ssh_auth_type': self.ssh_entries["认证方式:"].get(),
                'ssh_password': self.ssh_entries["SSH 密码:"].get(),
                'ssh_key_path': self.ssh_entries["私钥路径:"].get().strip(),
                'ssh_key_phrase': self.ssh_entries["私钥密码:"].get(),
                'ssh_local_port': int(self.ssh_entries["本地转发端口:"].get().strip()) if self.ssh_entries["本地转发端口:"].get().strip() else None,
                'ssh_remote_host': self.ssh_entries["远程数据库主机:"].get().strip(),
                'ssh_remote_port': int(self.ssh_entries["远程数据库端口:"].get().strip()) if self.ssh_entries["远程数据库端口:"].get().strip() else None
            })
            
            # 如果是编辑模式，必须保留原 ID，否则主窗口无法执行 UPDATE
            if self.conn_data and self.conn_data.get('id'):
                data['id'] = self.conn_data['id']
                
            return data
        except ValueError as e:
            messagebox.showerror("输入错误", "端口号必须是数字")
            return None

    def _on_ok(self):
        data = self._collect_data()
        if data:
            if not data['name']:
                messagebox.showwarning("输入错误", "连接名称不能为空")
                return
            # 连接名称重复检查：编辑模式排除自身
            current_id = data.get('id')
            storage = DBStorage()
            all_conns = storage.get_all_connections()
            for c in all_conns:
                if c['name'] == data['name'] and c['id'] != current_id:
                    messagebox.showwarning("名称重复", f"连接名称「{data['name']}」已存在，请使用其他名称")
                    return
            self.result = data
            self.destroy()

    def _test_ssh(self):
        data = self._collect_data()
        if not data: return
        if not data['ssh_host']:
            messagebox.showwarning("输入错误", "SSH 主机不能为空")
            return
        
        success, msg = SSHTunnelManager().test_ssh_connection(data)
        if success:
            messagebox.showinfo("测试成功", msg)
        else:
            messagebox.showerror("测试失败", msg)

    def _test_db(self):
        data = self._collect_data()
        if not data: return
        
        msg = "正在尝试建立连接 (含 SSH 隧道)..." if data.get('ssh_enabled') else "正在尝试建立连接..."
        progress = ProgressDialog(self, message=msg)
        
        def run_test():
            # 临时建立隧道并测试
            try:
                success, msg = self.db_ops.test_connection(data)
                self.after(0, lambda: self._on_test_done(progress, success, msg))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda m=err_msg: self._on_test_done(progress, False, m))
            finally:
                pass

        threading.Thread(target=run_test, daemon=True).start()

    def _on_test_done(self, progress, success, msg):
        progress.close()
        if success:
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("失败", msg)
