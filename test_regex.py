# -*- coding: utf-8 -*-
import re

# Simulate the exact text from context_builder.py
structures_count = 5
line = f"\n以下是对话中涉及的 {structures_count} 个表的结构信息：\n"
print('line         :', repr(line))

# The regex from ai.py
pattern = r'涉及 (\d+) 个表的结构信息'
print('pattern      :', repr(pattern))

match = re.search(pattern, line)
print('match        :', match)

if match:
    print('loaded_count :', int(match.group(1)))

# Also test with full context text
lines = []
lines.append(f"数据库类型: MySQL")
lines.append(f"数据库名: test_db")
lines.append(f"\n以下是对话中涉及的 {structures_count} 个表的结构信息：\n")
for t in ['users', 'orders']:
    lines.append(f"表名: {t}")
    lines.append(f"  - id INT ...")
context_text = "\n".join(lines)
print('\n--- Full context ---')
print(context_text)
match2 = re.search(pattern, context_text)
print('full match    :', match2)
if match2:
    print('loaded_count  :', int(match2.group(1)))
