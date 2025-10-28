import os, sys, traceback, importlib

root = os.path.dirname(os.path.dirname(__file__))
# Ensure the repository root is on sys.path so imports like 'game' work
if root not in sys.path:
    sys.path.insert(0, root)
errors = []
for dirpath, dirs, files in os.walk(root):
    if "__pycache__" in dirpath:
        continue
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(dirpath, f)
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    src = fh.read()
                compile(src, p, "exec")
            except Exception:
                errors.append((p, traceback.format_exc()))

if not errors:
    print("COMPILE_OK")
else:
    print(f"COMPILE_ERRORS: {len(errors)}")
    for p, tr in errors:
        print("\n---- SYNTAX ERROR in", p)
        print(tr)

# Try importing core modules
mods = [
    "game",
    "game.entities",
    "game.town",
    "game.companion",
    "game.save",
    "game.labyrinth",
    "game.engine",
]
for m in mods:
    try:
        importlib.invalidate_caches()
        mod = importlib.import_module(m)
        importlib.reload(mod)
        print("IMPORTED", m)
    except Exception:
        print("\n---- IMPORT FAIL", m)
        traceback.print_exc()

print("\nDone")
