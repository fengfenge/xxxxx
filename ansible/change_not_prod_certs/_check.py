import yaml

with open(r'e:\pythonProject\ansible\change_not_prod_certs\change_certs.yaml', encoding='utf-8') as f:
    content = f.read()
    docs = list(yaml.safe_load_all(content))

# 获取 handlers 部分
play = docs[0][0]
handlers = play.get('handlers', [])

print("Handlers 详细内容:")
for i, handler in enumerate(handlers):
    print(f"\nHandler {i}:")
    for key, value in handler.items():
        print(f"  {key}: {value!r}")

# 检查 notify 部分
tasks = play.get('tasks', [])
print("\n" + "="*50)
print("Tasks with notify:")
for i, task in enumerate(tasks):
    if 'notify' in task:
        print(f"\nTask {i}: {task.get('name')}")
        print(f"  notify: {task['notify']!r}")