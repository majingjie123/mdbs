"""基于 Tkinter Text tag 系统的 Markdown 渲染器"""

import tkinter as tk
import re


class MarkdownRenderer:
    """在 Tkinter Text widget 中渲染 Markdown 格式文本"""

    # 默认颜色方案（优化后的配色，更适合灰白背景）
    COLORS = {
        'heading_fg': '#1a1a2e',
        'bold_fg': '#2d2d2d',
        'italic_fg': '#555555',
        'code_bg': '#f0f0f0',
        'code_fg': '#c7254e',
        'code_block_bg': '#282c34',
        'code_block_fg': '#abb2bf',
        'link_fg': '#1a73e8',
        'list_fg': '#333333',
        'table_border': '#e0e0e0',
        'table_header_bg': '#f5f5f5',
        'table_cell_fg': '#333333',
        'table_alt_bg': '#fafafa',
        'blockquote_fg': '#666666',
        'blockquote_border': '#cccccc',
        'hr_fg': '#dddddd',
        'strikethrough_fg': '#999999',
    }

    # 默认字体
    FONTS = {
        'normal': ('Microsoft YaHei', 10),
        'heading1': ('Microsoft YaHei', 14, 'bold'),
        'heading2': ('Microsoft YaHei', 12, 'bold'),
        'heading3': ('Microsoft YaHei', 11, 'bold'),
        'code': ('Consolas', 10),
        'code_block': ('Consolas', 9),
        'bold': ('Microsoft YaHei', 10, 'bold'),
        'italic': ('Microsoft YaHei', 10, 'italic'),
    }

    def __init__(self, text_widget, colors=None, fonts=None):
        """
        :param text_widget: tk.Text 控件
        :param colors: 颜色覆盖字典
        :param fonts: 字体覆盖字典
        """
        self.text = text_widget
        self.colors = {**self.COLORS, **(colors or {})}
        self.fonts = {**self.FONTS, **(fonts or {})}
        self._setup_tags()

    def _setup_tags(self):
        """配置 Text widget 的 tag 样式"""
        self.text.tag_configure('heading1', font=self.fonts['heading1'],
                                foreground=self.colors['heading_fg'], spacing3=4)
        self.text.tag_configure('heading2', font=self.fonts['heading2'],
                                foreground=self.colors['heading_fg'], spacing3=3)
        self.text.tag_configure('heading3', font=self.fonts['heading3'],
                                foreground=self.colors['heading_fg'], spacing3=2)
        self.text.tag_configure('bold', font=self.fonts['bold'],
                                foreground=self.colors['bold_fg'])
        self.text.tag_configure('italic', font=self.fonts['italic'],
                                foreground=self.colors['italic_fg'])
        self.text.tag_configure('strikethrough', font=self.fonts['normal'],
                                foreground=self.colors['strikethrough_fg'],
                                overstrike=True)
        self.text.tag_configure('code', font=self.fonts['code'],
                                foreground=self.colors['code_fg'],
                                background=self.colors['code_bg'])
        self.text.tag_configure('code_block', font=self.fonts['code_block'],
                                foreground=self.colors['code_block_fg'],
                                background=self.colors['code_block_bg'],
                                lmargin1=10, lmargin2=10,
                                spacing1=4, spacing3=4)
        self.text.tag_configure('code_header', font=('Microsoft YaHei', 8),
                                foreground='#666666', background='#e8e8e8',
                                lmargin1=10, lmargin2=10, spacing1=2)
        self.text.tag_configure('copy_link', font=('Microsoft YaHei', 8, 'underline'),
                                foreground='#1a73e8', background='#e8e8e8')
        self.text.tag_configure('link', font=self.fonts['normal'],
                                foreground=self.colors['link_fg'],
                                underline=True)
        self.text.tag_configure('list_item', font=self.fonts['normal'],
                                foreground=self.colors['list_fg'],
                                lmargin1=15, lmargin2=25)
        self.text.tag_configure('blockquote', font=self.fonts['normal'],
                                foreground=self.colors['blockquote_fg'],
                                lmargin1=15, lmargin2=15,
                                relief='flat', borderwidth=0)
        self.text.tag_configure('hr', font=('Microsoft YaHei', 1),
                                foreground=self.colors['hr_fg'],
                                spacing1=6, spacing3=6)
        self.text.tag_configure('table_header', font=('Microsoft YaHei', 9, 'bold'),
                                foreground=self.colors['table_cell_fg'],
                                background=self.colors['table_header_bg'],
                                lmargin1=10, lmargin2=10)
        self.text.tag_configure('table_cell', font=('Microsoft YaHei', 9),
                                foreground=self.colors['table_cell_fg'],
                                lmargin1=10, lmargin2=10)
        self.text.tag_configure('table_cell_alt', font=('Microsoft YaHei', 9),
                                foreground=self.colors['table_cell_fg'],
                                background=self.colors['table_alt_bg'],
                                lmargin1=10, lmargin2=10)
        self.text.tag_configure('normal', font=self.fonts['normal'])
        self.text.tag_configure('copy_button', font=('Consolas', 8),
                                foreground='#888888', justify='right')

    def render(self, markdown_text, start_pos=None):
        """
        渲染 Markdown 文本到 Text widget
        :param markdown_text: Markdown 格式的文本
        :param start_pos: 插入位置，None 表示追加到末尾
        """
        if not markdown_text:
            return

        self.text.configure(state="normal")

        if start_pos is None:
            start_pos = self.text.index("end-1c")

        lines = markdown_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            # 代码块
            if line.strip().startswith('```'):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                code_text = '\n'.join(code_lines)
                if code_text:
                    # 插入代码块页眉（含复制按钮）
                    self.text.insert("end", " 代码块 ", "code_header")
                    self.text.insert("end", "[复制]", "copy_link")
                    self.text.insert("end", "\n")
                    # 插入代码内容
                    self.text.insert("end", code_text + "\n", "code_block")
                i += 1
                continue

            # 标题
            heading_match = re.match(r'^(#{1,3})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                tag = f'heading{level}'
                self.text.insert("end", content + "\n", tag)
                i += 1
                continue

            # 引用块
            if line.strip().startswith('>'):
                content = re.sub(r'^>\s*', '', line.strip())
                self.text.insert("end", content + "\n", "blockquote")
                i += 1
                continue

            # 无序列表
            list_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
            if list_match:
                indent = len(list_match.group(1))
                content = list_match.group(2)
                bullet = "  " * (indent // 2) + "• "
                self._render_inline(bullet + content + "\n", "list_item")
                i += 1
                continue

            # 有序列表
            ordered_match = re.match(r'^(\s*)(\d+)[.)]\s+(.+)$', line)
            if ordered_match:
                indent = len(ordered_match.group(1))
                num = ordered_match.group(2)
                content = ordered_match.group(3)
                prefix = "  " * (indent // 2) + f"{num}. "
                self._render_inline(prefix + content + "\n", "list_item")
                i += 1
                continue

            # 分隔线 (---, ***, ___)
            if re.match(r'^[-*_]{3,}\s*$', line):
                self.text.insert("end", "─" * 50 + "\n", "hr")
                i += 1
                continue

            # 表格检测（当前行以 | 开头且下一行是分隔行）
            if line.strip().startswith('|') and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.match(r'^\|[\s\-:|]+\|$', next_line):
                    self._render_table(lines, i)
                    # 找到表格结束位置
                    while i < len(lines) and lines[i].strip().startswith('|'):
                        i += 1
                    continue

            # 空行
            if not line.strip():
                self.text.insert("end", "\n", "normal")
                i += 1
                continue

            # 普通段落（含行内格式）
            self._render_inline(line + "\n", "normal")
            i += 1

    def _render_inline(self, text, base_tag):
        """渲染行内格式（粗体、斜体、删除线、行内代码、链接）"""
        # 分词解析：行内代码 > 粗体 > 斜体 > 删除线 > 链接 > 普通文本
        parts = self._parse_inline(text)
        for tag, content in parts:
            if tag == 'code':
                self.text.insert("end", content, "code")
            elif tag == 'bold':
                self.text.insert("end", content, "bold")
            elif tag == 'italic':
                self.text.insert("end", content, "italic")
            elif tag == 'strikethrough':
                self.text.insert("end", content, "strikethrough")
            elif tag == 'link':
                self.text.insert("end", content, "link")
            else:
                self.text.insert("end", content, base_tag)

    def _render_table(self, lines, start_idx):
        """渲染 Markdown 表格"""
        # 解析表头
        header_line = lines[start_idx].strip()
        headers = [h.strip() for h in header_line.strip('|').split('|')]

        # 跳过表头分隔行
        # start_idx + 1 是分隔行（如 |---|---|），已在外层验证

        # 收集数据行
        data_lines = []
        idx = start_idx + 2
        while idx < len(lines) and lines[idx].strip().startswith('|'):
            data_lines.append(lines[idx].strip())
            idx += 1

        # 渲染表头
        header_text = ' | '.join(headers) + '\n'
        self.text.insert("end", header_text, "table_header")

        # 渲染数据行
        for row_idx, row_line in enumerate(data_lines):
            cells = [c.strip() for c in row_line.strip('|').split('|')]
            row_text = ' | '.join(cells) + '\n'
            tag = 'table_cell_alt' if row_idx % 2 == 1 else 'table_cell'
            self.text.insert("end", row_text, tag)

        # 表格后空一行
        self.text.insert("end", "\n", "normal")

    def _parse_inline(self, text):
        """解析行内 Markdown 格式，返回 (tag, content) 列表"""
        parts = []
        # 用正则逐段匹配
        pattern = re.compile(
            r'(?P<code>`[^`]+`)'              # 行内代码
            r'|(?P<bold>\*\*[^*]+\*\*)'        # 粗体
            r'|(?P<italic>\*[^*]+\*)'          # 斜体
            r'|(?P<strikethrough>~~[^~]+~~)'   # 删除线
            r'|(?P<link>\[[^\]]+\]\([^)]+\))'  # 链接
        )

        last_end = 0
        for m in pattern.finditer(text):
            # 匹配前的普通文本
            if m.start() > last_end:
                parts.append(('normal', text[last_end:m.start()]))

            if m.group('code'):
                content = m.group('code')[1:-1]  # 去掉反引号
                parts.append(('code', content))
            elif m.group('bold'):
                content = m.group('bold')[2:-2]  # 去掉 **
                parts.append(('bold', content))
            elif m.group('italic'):
                content = m.group('italic')[1:-1]  # 去掉 *
                parts.append(('italic', content))
            elif m.group('strikethrough'):
                content = m.group('strikethrough')[2:-2]  # 去掉 ~~
                parts.append(('strikethrough', content))
            elif m.group('link'):
                # 提取显示文本
                link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', m.group('link'))
                if link_match:
                    parts.append(('link', link_match.group(1)))
                else:
                    parts.append(('normal', m.group('link')))

            last_end = m.end()

        # 剩余文本
        if last_end < len(text):
            parts.append(('normal', text[last_end:]))

        return parts if parts else [('normal', text)]
