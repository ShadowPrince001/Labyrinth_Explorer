import pkgutil
import importlib
import traceback
import os
import sys

# Ensure repo root is on sys.path so 'import game' works when running from tools/
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

failed = []
for finder, name, ispkg in pkgutil.iter_modules([os.path.join(REPO_ROOT, 'game')]):
    modname = 'game.' + name
    try:
        importlib.import_module(modname)
        print(modname, 'OK')
    except Exception:
        print(modname, 'ERROR')
        traceback.print_exc()
        failed.append(modname)

print('\nImport check complete. Failed modules:', failed)
