import json, re, os

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(ROOT, 'data')

def load_json(name):
    path = os.path.join(DATA, name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {}

# Collect item names from data files
weapons = [w.get('name') for w in load_json('weapons.json') or [] if w.get('name')]
armors = [a.get('name') for a in load_json('armors.json') or [] if a.get('name')]
potions = [p.get('name') for p in load_json('potions.json') or [] if p.get('name')]
spells = [s.get('name') for s in load_json('spells.json') or [] if s.get('name')]
magic = [m.get('name') for m in load_json('magic_items.json') or [] if m.get('name')]

all_items = set([*(weapons or []), *(armors or []), *(potions or []), *(spells or []), *(magic or [])])

# Load dialogues and gather all strings
dialogues = load_json('dialogues.json') or {}

strings = []

def collect_strings(node):
    if isinstance(node, str):
        strings.append(node)
    elif isinstance(node, list):
        for v in node:
            collect_strings(v)
    elif isinstance(node, dict):
        for v in node.values():
            collect_strings(v)

collect_strings(dialogues)

# regex to find Title Case phrases (1-3 words)
phrase_re = re.compile(r"\b([A-Z][a-z0-9']+(?:\s+[A-Z][a-z0-9']+){0,2})\b")

candidates = {}
common = set(['The','You','Your','May','In','A','An','It','And','For','Of','To','Back','Gold','Quest','Town','Shop','Ring','Armor','Weapon','Potion','Spell'])

for s in strings:
    for m in phrase_re.findall(s):
        if m in common:
            continue
        candidates[m] = candidates.get(m, 0) + 1

# Now find candidates that are not in all_items
suspects = [(name, cnt) for name,cnt in candidates.items() if name not in all_items]

suspects.sort(key=lambda x: -x[1])

print('=== Found item-like phrases in dialogues that are NOT present in current data files ===')
for name, cnt in suspects[:200]:
    print(f"{name}  (occurrences: {cnt})")

print('\nTotal data item names: %d' % len(all_items))
print('Sample data names:')
for n in list(all_items)[:50]:
    print(' - ' + n)
