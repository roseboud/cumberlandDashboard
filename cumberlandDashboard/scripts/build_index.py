import os
os.chdir('cumberlandDashboard')
parts = []
for i in range(1, 6):
    with open(f'parts/part{i}.html', 'r', encoding='utf-8') as f:
        parts.append(f.read())
with open('index.html', 'w', encoding='utf-8') as f:
    f.write('\n'.join(parts))
size = os.path.getsize('index.html')
print(f'index.html rebuilt ({size} bytes)')
