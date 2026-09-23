import ast
try:
    with open('smart_search_router.py', 'r', encoding='utf-8') as f:
        source = f.read()
    ast.parse(source)
    print("Parsed successfully!")
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}, offset {e.offset}: {e.msg}")
