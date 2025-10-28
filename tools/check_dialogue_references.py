import os
import re
import json
import sys
from typing import Dict, Any, List, Tuple

ROOT = os.path.dirname(os.path.dirname(__file__))
DIALOGUES_PATH = os.path.join(ROOT, "data", "dialogues.json")
CODE_ROOT = os.path.join(ROOT, "game")
# Legacy CLI modules that still use print/input; exclude by default from this check
DEFAULT_EXCLUDE_BASENAMES = {
    "__main__.py",
    "town.py",
    "shop.py",
    "combat.py",
    "dungeon.py",
    "magic_items.py",
    "companion.py",
}

# Regex patterns to capture dialogue lookups
RE_GET_DIALOGUE = re.compile(
    r"get_dialogue\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
)
RE_GET_NPC_DIALOGUE = re.compile(
    r"get_npc_dialogue\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
)


def load_dialogues() -> Dict[str, Any]:
    with open(DIALOGUES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def file_paths(base: str, exclude: set) -> List[str]:
    paths: List[str] = []
    for dirpath, _, files in os.walk(base):
        if "__pycache__" in dirpath:
            continue
        for name in files:
            if name.endswith(".py") and name not in exclude:
                paths.append(os.path.join(dirpath, name))
    return paths


def collect_references(
    include_cli: bool = False,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str]]]:
    dlg_refs: List[Tuple[str, str]] = []
    npc_refs: List[Tuple[str, str, str]] = []
    exclude = set() if include_cli else set(DEFAULT_EXCLUDE_BASENAMES)
    for path in file_paths(CODE_ROOT, exclude):
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            continue
        for m in RE_GET_DIALOGUE.finditer(text):
            dlg_refs.append((m.group(1), m.group(2)))
        for m in RE_GET_NPC_DIALOGUE.finditer(text):
            npc_refs.append((m.group(1), m.group(2), m.group(3)))
    # De-duplicate while preserving order
    seen = set()
    dlg_unique: List[Tuple[str, str]] = []
    for k in dlg_refs:
        if k not in seen:
            dlg_unique.append(k)
            seen.add(k)
    seen2 = set()
    npc_unique: List[Tuple[str, str, str]] = []
    for k in npc_refs:
        if k not in seen2:
            npc_unique.append(k)
            seen2.add(k)
    return dlg_unique, npc_unique


def path_exists(d: Dict[str, Any], keys: List[str]) -> bool:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    # Leaf can be str or nested dict (acceptable for NPC categories etc.)
    return True


def main() -> int:
    dialogues = load_dialogues()
    include_cli = any(arg in ("--include-cli", "-a", "--all") for arg in sys.argv[1:])
    dlg_refs, npc_refs = collect_references(include_cli=include_cli)

    missing_simple: List[Tuple[str, str]] = []
    for sec, key in dlg_refs:
        if not path_exists(dialogues, [sec, key]):
            missing_simple.append((sec, key))

    missing_npc: List[Tuple[str, str, str]] = []
    for sec, npc, sub in npc_refs:
        if not path_exists(dialogues, [sec, npc, sub]):
            missing_npc.append((sec, npc, sub))

    print(f"Scanned files under: {CODE_ROOT}")
    if include_cli:
        print("Including legacy CLI modules in scan: YES")
    else:
        print("Including legacy CLI modules in scan: NO (use --include-cli to include)")
    print(f"Found get_dialogue refs: {len(dlg_refs)} (unique {len(set(dlg_refs))})")
    print(f"Found get_npc_dialogue refs: {len(npc_refs)} (unique {len(set(npc_refs))})")
    print(f"Dialogues sections: {len(dialogues.keys())}")

    if not missing_simple and not missing_npc:
        print(
            "DIALOGUE_REFERENCES_OK: All referenced keys exist in data/dialogues.json"
        )
        return 0

    if missing_simple:
        print(f"\nMissing simple dialogue keys ({len(missing_simple)}):")
        for sec, key in sorted(missing_simple):
            print(f"  - {sec}.{key}")

    if missing_npc:
        print(f"\nMissing NPC dialogue keys ({len(missing_npc)}):")
        for sec, npc, sub in sorted(missing_npc):
            print(f"  - {sec}.{npc}.{sub}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
