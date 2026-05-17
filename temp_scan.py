import ast
with open(r'D:\code\innox\DBConnectorManager\core\importer.py', encoding='utf-8') as f:
    tree = ast.parse(f.read())
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == 'Importer':
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                print(f'  {item.name}')
