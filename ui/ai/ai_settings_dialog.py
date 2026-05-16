"""AI 配置管理 — 列表窗口 + 编辑弹窗"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from models.db_storage import DBStorage
from core.ai.client import AIClient


class AIConfigEditDialog(tk.Toplevel):
    """AI 配置编辑弹窗（新增/编辑共用）"""

    def __init__(self, parent, config_data=None, on_saved=None):
        """
        :param parent: 父窗口
        :param config_data: 已有配置字典（编辑模式），None 为新增模式
        :param on_saved: 保存成功回调 on_saved(config_id)
        """
        super().__init__(parent)
        self.title("编辑 AI 配置" if config_data else "新增 AI 配置")
        self.parent = parent
        self.on_saved = on_saved
        self.storage = DBStorage()
        self._editing_id = config_data.get('id') if config_data else None

        width, height = 560, 530
        self.minsize(480, 400)
        self.resizable(True, True)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self._init_ui()

        # 编辑模式：填充已有数据
        if config_data:
            self._fill_form(config_data)

        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        """构建编辑表单"""
        form = ttk.Frame(self, padding=15)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(form, text="配置名称:").grid(row=row, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=35).grid(row=row, column=1, sticky="ew", pady=4)
        self.name_var_widget = form.winfo_children()[-1]

        row += 1
        ttk.Label(form, text="协议类型:").grid(row=row, column=0, sticky="w", pady=4)
        self.protocol_var = tk.StringVar(value='openai')
        ttk.Combobox(form, textvariable=self.protocol_var,
                      values=['openai'], state='readonly', width=15).grid(row=row, column=1, sticky="w", pady=4)

        row += 1
        ttk.Label(form, text="API Key:").grid(row=row, column=0, sticky="w", pady=4)
        key_frame = ttk.Frame(form)
        key_frame.grid(row=row, column=1, sticky="ew", pady=4)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, show="*", width=28)
        self.api_key_entry.pack(side="left", fill="x", expand=True)
        self._show_key = False
        self.toggle_key_btn = ttk.Button(key_frame, text="👁", width=3, command=self._toggle_api_key)
        self.toggle_key_btn.pack(side="right", padx=(3, 0))

        row += 1
        ttk.Label(form, text="Base URL:").grid(row=row, column=0, sticky="w", pady=4)
        self.base_url_var = tk.StringVar(value='https://api.openai.com/v1')
        ttk.Entry(form, textvariable=self.base_url_var, width=35).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(form, text="模型名称:").grid(row=row, column=0, sticky="w", pady=4)
        model_frame = ttk.Frame(form)
        model_frame.grid(row=row, column=1, sticky="ew", pady=4)
        self.model_var = tk.StringVar(value='gpt-3.5-turbo')
        self._all_models = []
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, width=22)
        self.model_combo.pack(side="left", fill="x", expand=True)
        self.model_combo.bind('<KeyRelease>', self._on_model_key)
        self.refresh_models_btn = ttk.Button(model_frame, text="获取模型列表", command=self._refresh_models)
        self.refresh_models_btn.pack(side="right", padx=(5, 0))

        row += 1
        ttk.Label(form, text="系统提示词:").grid(row=row, column=0, sticky="nw", pady=4)
        self.system_prompt_text = tk.Text(form, width=33, height=3, wrap="word")
        self.system_prompt_text.grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(form, text="Temperature:").grid(row=row, column=0, sticky="w", pady=4)
        temp_frame = ttk.Frame(form)
        temp_frame.grid(row=row, column=1, sticky="ew", pady=4)
        self.temp_var = tk.DoubleVar(value=0.7)
        self.temp_scale = ttk.Scale(temp_frame, from_=0, to=2, variable=self.temp_var,
                                     orient="horizontal", command=self._on_temp_change)
        self.temp_scale.pack(side="left", fill="x", expand=True)
        self.temp_label = ttk.Label(temp_frame, text="0.7", width=4)
        self.temp_label.pack(side="right", padx=(5, 0))

        row += 1
        ttk.Label(form, text="Max Tokens:").grid(row=row, column=0, sticky="w", pady=4)
        self.max_tokens_var = tk.IntVar(value=2048)
        ttk.Spinbox(form, textvariable=self.max_tokens_var,
                     from_=1, to=128000, width=10).grid(row=row, column=1, sticky="w", pady=4)

        row += 1
        self.default_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="设为默认配置", variable=self.default_var).grid(row=row, column=1, sticky="w", pady=4)

        # 底部按钮
        btn_frame = ttk.Frame(self, padding=(15, 5, 15, 10))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="测试连接", command=self._test_connection).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="保存", command=self._save, style="BigAction.TButton").pack(side="right", padx=3)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=3)

    def _fill_form(self, cfg):
        """填充已有配置数据"""
        self.name_var.set(cfg.get('name', ''))
        self.protocol_var.set(cfg.get('protocol', 'openai'))
        self.api_key_var.set(cfg.get('api_key', ''))
        self.base_url_var.set(cfg.get('base_url', 'https://api.openai.com/v1'))
        self.model_var.set(cfg.get('model', 'gpt-3.5-turbo'))
        self.system_prompt_text.delete("1.0", "end")
        self.system_prompt_text.insert("1.0", cfg.get('system_prompt', ''))
        self.temp_var.set(float(cfg.get('temperature', 0.7)))
        self.temp_label.configure(text=f"{float(cfg.get('temperature', 0.7)):.1f}")
        self.max_tokens_var.set(int(cfg.get('max_tokens', 2048)))
        self.default_var.set(bool(cfg.get('is_default', 0)))

    def _get_form_data(self):
        """获取表单数据"""
        return {
            'id': self._editing_id,
            'name': self.name_var.get().strip(),
            'protocol': self.protocol_var.get(),
            'api_key': self.api_key_var.get().strip(),
            'base_url': self.base_url_var.get().strip() or 'https://api.openai.com/v1',
            'model': self.model_var.get().strip() or 'gpt-3.5-turbo',
            'system_prompt': self.system_prompt_text.get("1.0", "end-1c").strip(),
            'temperature': self.temp_var.get(),
            'max_tokens': self.max_tokens_var.get(),
            'is_default': 1 if self.default_var.get() else 0
        }

    # ---- 交互 ----

    def _toggle_api_key(self):
        """切换 API Key 显示/隐藏"""
        self._show_key = not self._show_key
        self.api_key_entry.configure(show="" if self._show_key else "*")
        self.toggle_key_btn.configure(text="🔒" if self._show_key else "👁")

    def _on_temp_change(self, val):
        self.temp_label.configure(text=f"{float(val):.1f}")

    def _refresh_models(self):
        """根据 Base URL + API Key 实时拉取模型列表"""
        api_key = self.api_key_var.get().strip()
        base_url = self.base_url_var.get().strip() or 'https://api.openai.com/v1'
        if not api_key:
            messagebox.showwarning("提示", "请先输入 API Key", parent=self)
            return

        self.refresh_models_btn.configure(state="disabled", text="获取中...")

        def run():
            success, result = AIClient.list_models({'api_key': api_key, 'base_url': base_url})
            self.after(0, lambda: self._on_models_loaded(success, result))

        threading.Thread(target=run, daemon=True).start()

    def _on_models_loaded(self, success, result):
        if not self.refresh_models_btn.winfo_exists():
            return
        self.refresh_models_btn.configure(state="normal", text="获取模型列表")
        if success:
            if not result:
                messagebox.showinfo("提示", "该接口未返回任何模型", parent=self)
                return
            self._all_models = result
            current = self.model_var.get()
            self.model_combo['values'] = result
            if current not in result:
                self.model_var.set(result[0])
        else:
            messagebox.showerror("错误", result, parent=self)

    def _on_model_key(self, event):
        """模型名称输入时实时过滤下拉列表"""
        # 忽略方向键和回车键，避免干扰选择操作
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'):
            return
        keyword = self.model_var.get().strip().lower()
        if not self._all_models:
            return
        if not keyword:
            self.model_combo['values'] = self._all_models
        else:
            filtered = [m for m in self._all_models if keyword in m.lower()]
            self.model_combo['values'] = filtered
        # 延迟弹出下拉列表，让 Combobox 先更新内部状态
        self.after(10, lambda: self.model_combo.event_generate('<Down>'))

    def _test_connection(self):
        """测试连接"""
        data = self._get_form_data()
        if not data['api_key']:
            messagebox.showwarning("提示", "请先输入 API Key", parent=self)
            return

        self._test_btn = None
        for w in self.winfo_children():
            if isinstance(w, ttk.Frame):
                for btn in w.winfo_children():
                    if isinstance(btn, ttk.Button) and btn.cget('text') == '测试连接':
                        btn.configure(state="disabled", text="测试中...")
                        self._test_btn = btn
                        break

        def run():
            client = AIClient(data)
            success, msg = client.test_connection()
            self.after(0, lambda: self._on_test_result(success, msg))

        threading.Thread(target=run, daemon=True).start()

    def _on_test_result(self, success, msg):
        if hasattr(self, '_test_btn') and self._test_btn and self._test_btn.winfo_exists():
            self._test_btn.configure(state="normal", text="测试连接")
        if success:
            messagebox.showinfo("测试连接", f"✓ {msg}", parent=self)
        else:
            messagebox.showerror("测试连接", f"✗ {msg}", parent=self)

    def _save(self):
        """保存配置"""
        data = self._get_form_data()
        if not data['name']:
            messagebox.showwarning("提示", "请输入配置名称", parent=self)
            return
        if not data['api_key']:
            messagebox.showwarning("提示", "请输入 API Key", parent=self)
            return

        config_id = self.storage.save_ai_config(data)
        self._editing_id = config_id

        # 先释放模态锁定并关闭窗口，再通知父窗口刷新列表
        on_saved = self.on_saved
        self.grab_release()
        self.destroy()

        if on_saved:
            on_saved(config_id)


class AISettingsDialog(tk.Toplevel):
    """AI 配置列表窗口 — 显示已配置列表，新增/双击弹出编辑窗口"""

    def __init__(self, parent, on_configs_changed=None):
        super().__init__(parent)
        self.title("AI 配置管理")
        self.parent = parent
        self._on_configs_changed = on_configs_changed

        width, height = 500, 420
        self.minsize(420, 300)
        self.resizable(True, True)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.storage = DBStorage()

        self._init_ui()
        self._load_list()

        self.transient(parent)
        self.grab_set()

    def _init_ui(self):
        """构建列表界面"""
        # 列表区
        list_frame = ttk.Frame(self, padding=10)
        list_frame.pack(fill="both", expand=True)

        # 工具栏
        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="➕ 新增", command=self._add_config).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🗑 删除", command=self._delete_config).pack(side="left", padx=2)
        ttk.Button(toolbar, text="⭐ 设为默认", command=self._set_default).pack(side="left", padx=2)
        ttk.Label(toolbar, text="双击编辑配置", font=("Microsoft YaHei", 8), foreground="#888").pack(side="right", padx=5)

        # Treeview
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill="both", expand=True)

        self.config_tree = ttk.Treeview(tree_frame, columns=('name', 'protocol', 'model', 'is_default'),
                                         show='headings', height=12)
        self.config_tree.heading('name', text='名称')
        self.config_tree.heading('protocol', text='协议')
        self.config_tree.heading('model', text='模型')
        self.config_tree.heading('is_default', text='默认')
        self.config_tree.column('name', width=120)
        self.config_tree.column('protocol', width=60)
        self.config_tree.column('model', width=160)
        self.config_tree.column('is_default', width=40, anchor='center')
        self.config_tree.pack(side="left", fill="both", expand=True)
        self.config_tree.bind('<Double-1>', self._on_double_click)
        self.config_tree.bind('<Button-3>', self._show_context_menu)

        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="✏ 编辑", command=self._edit_selected)
        self.context_menu.add_command(label="🗑 删除", command=self._delete_config)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="⭐ 设为默认", command=self._set_default)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.config_tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.config_tree.configure(yscrollcommand=tree_scroll.set)

        # 底部关闭按钮
        btn_frame = ttk.Frame(self, padding=(10, 5, 10, 10))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side="right", padx=3)

    def _load_list(self):
        """刷新配置列表"""
        self.config_tree.delete(*self.config_tree.get_children())
        configs = self.storage.get_ai_configs()
        for cfg in configs:
            default_mark = "★" if cfg.get('is_default') else ""
            self.config_tree.insert('', 'end', iid=str(cfg['id']),
                                     values=(cfg['name'], cfg.get('protocol', 'openai'),
                                             cfg.get('model', ''), default_mark))

    def _get_selected_id(self):
        """获取当前选中的配置 ID"""
        sel = self.config_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _show_context_menu(self, event):
        """右键菜单"""
        item = self.config_tree.identify_row(event.y)
        if not item:
            return
        self.config_tree.selection_set(item)
        self.context_menu.post(event.x_root, event.y_root)

    def _edit_selected(self):
        """编辑选中的配置（右键菜单触发）"""
        config_id = self._get_selected_id()
        if config_id is None:
            return
        cfg = self.storage.get_ai_config(config_id)
        if cfg:
            AIConfigEditDialog(self, config_data=cfg, on_saved=self._on_config_saved)

    def _add_config(self):
        """新增配置 — 弹出编辑窗口"""
        AIConfigEditDialog(self, config_data=None, on_saved=self._on_config_saved)

    def _on_config_saved(self, config_id):
        """编辑窗口保存成功回调"""
        self._load_list()
        # 选中刚保存的项
        try:
            self.config_tree.selection_set(str(config_id))
            self.config_tree.see(str(config_id))
        except Exception:
            pass
        # 通知外部刷新
        if self._on_configs_changed:
            self._on_configs_changed()

    def _on_double_click(self, event):
        """双击编辑配置"""
        config_id = self._get_selected_id()
        if config_id is None:
            return
        cfg = self.storage.get_ai_config(config_id)
        if cfg:
            AIConfigEditDialog(self, config_data=cfg, on_saved=self._on_config_saved)

    def _delete_config(self):
        """删除配置"""
        config_id = self._get_selected_id()
        if config_id is None:
            messagebox.showinfo("提示", "请先选择一个配置", parent=self)
            return
        if not messagebox.askyesno("确认", "确定要删除此配置吗？", parent=self):
            return
        self.storage.delete_ai_config(config_id)
        self._load_list()
        if self._on_configs_changed:
            self._on_configs_changed()

    def _set_default(self):
        """设为默认配置"""
        config_id = self._get_selected_id()
        if config_id is None:
            messagebox.showinfo("提示", "请先选择一个配置", parent=self)
            return
        cfg = self.storage.get_ai_config(config_id)
        if cfg:
            cfg['is_default'] = 1
            self.storage.save_ai_config(cfg)
            self._load_list()
            if self._on_configs_changed:
                self._on_configs_changed()
