import os, json, re, time

root = r"c:\Users\Maheeyan Saha\Downloads\DnD"
# Load dialogues
with open(os.path.join(root, 'data', 'dialogues.json'), 'r', encoding='utf-8') as f:
    dialogues = json.load(f)

# Build dialogue map
dialogue_map = {}
for ns, node in dialogues.items():
    if isinstance(node, dict):
        dialogue_map[ns] = list(node.keys())

# Gather files to scan
files = []
for dp, dns, fns in os.walk(root):
    for fn in fns:
        if fn.endswith(('.py', '.html', '.txt')):
            files.append(os.path.join(dp, fn))

# Patterns for literal calls
p_get = re.compile(r"get_dialogue\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
p_npc = re.compile(r"get_npc_dialogue\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]")

usage = {}
for f in files:
    try:
        txt = open(f, 'r', encoding='utf-8').read()
    except Exception:
        continue
    for m in p_get.finditer(txt):
        ns, k = m.group(1), m.group(2)
        usage.setdefault((ns, k), []).append(f)
    for m in p_npc.finditer(txt):
        ns, k = m.group(1), m.group(2)
        usage.setdefault((ns, k), []).append(f)

report = {
    'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'method': 'conservative-literal-scan',
    'dialogues': dialogue_map,
    'dialogue_usage': {},
    'unused_dialogue_candidates': []
}

for ns, keys in dialogue_map.items():
    for k in keys:
        report['dialogue_usage'][f"{ns}::{k}"] = usage.get((ns, k), [])

for pair, files_used in report['dialogue_usage'].items():
    if not files_used:
        report['unused_dialogue_candidates'].append(pair)

out_path = os.path.join(root, 'tools', 'unused_report.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2)

print('WROTE', out_path)
print('UNUSED CANDIDATES:', len(report['unused_dialogue_candidates']))
