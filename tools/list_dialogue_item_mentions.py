import json, os

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(ROOT, 'data')

def load_json(name):
    path = os.path.join(DATA, name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

weapons = [w.get('name') for w in load_json('weapons.json') or [] if w.get('name')]
armors = [a.get('name') for a in load_json('armors.json') or [] if a.get('name')]
potions = [p.get('name') for p in load_json('potions.json') or [] if p.get('name')]
spells = [s.get('name') for s in load_json('spells.json') or [] if s.get('name')]
magic = [m.get('name') for m in load_json('magic_items.json') or [] if m.get('name')]

all_items = set([*(weapons or []), *(armors or []), *(potions or []), *(spells or []), *(magic or [])])

DIALOGUE = load_json('dialogues.json') or {}

results = []

# Walk dialogues recursively and check lines

def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, path + [k])
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + [str(i)])
    elif isinstance(node, str):
        text = node
        for item in all_items:
            if not item:
                continue
            # match whole word ignoring case
            import re
            if re.search(r"\b" + re.escape(item) + r"\b", text, flags=re.I):
                results.append(("/".join(path), item, text))
                # don't duplicate multiple items on same line
                break

walk(DIALOGUE, [])

# Print concise list
for path, item, text in results:
    print(f"{path} --> {item} --> {text}")

print(f"\nTotal matches: {len(results)}")
