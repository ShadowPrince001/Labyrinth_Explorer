import sys, os, importlib, traceback, json

# Ensure we import from the current repository root (parent of this tools/ dir)
root = os.path.dirname(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

modules = ["game.engine", "game.combat", "game.town", "web_app"]
results = {}
for m in modules:
    try:
        importlib.import_module(m)
        results[m] = "OK"
    except Exception:
        results[m] = "ERROR:\n" + traceback.format_exc()
print(json.dumps(results, indent=2))
