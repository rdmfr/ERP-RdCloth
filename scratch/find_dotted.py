import re

with open('backend/server.py', 'r', encoding='utf-8') as f:
    text = f.read()

finds = re.findall(r'find(?:_one)?\(\s*\{([^}]+)\}', text)
dotted = []
for f in finds:
    for m in re.findall(r'[\'\"]([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)[\'\"]', f):
        dotted.append(m)

print("Dotted keys in find():", set(dotted))
