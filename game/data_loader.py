import json
import os
from typing import Any, List, Union, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _read_json(filename: str) -> Any:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_weapons() -> List[dict]:
    return _read_json("weapons.json")


def load_armors() -> List[dict]:
    return _read_json("armors.json")


def load_monsters() -> List[dict]:
    return _read_json("monsters.json")


def load_classes() -> List[dict]:
    return _read_json("classes.json")


def load_spells() -> List[dict]:
    return _read_json("spells.json")


def load_potions() -> List[dict]:
    return _read_json("potions.json")


def load_monster_sounds() -> List[dict]:
    return _read_json("monster_sounds.json")


def load_traps() -> List[dict]:
    return _read_json("traps.json")


def load_magic_items() -> List[dict]:
    return _read_json("magic_items.json")


def load_monster_descriptions() -> dict:
    """Load monster text descriptions from data/monsters_desc.json.

    Returns a dict mapping monster name -> description string.
    """
    return _read_json("monsters_desc.json")


def load_dialogues() -> dict:
    """Load dialogues JSON as a dictionary.

    The file should be located at data/dialogues.json and contain structured
    entries under top-level keys (for example, 'town').
    """
    return _read_json("dialogues.json")


def get_dialogue(
    namespace: str, key: str, condition: Optional[str] = None, character=None
) -> str:
    """Return a single dialogue string chosen from data/dialogues.json.

    Parameters:
    - namespace: top-level category (e.g., 'town')
    - key: NPC key inside namespace (e.g., 'shopkeeper_mara')
    - condition: optional condition name (e.g., 'no_gold', 'full_health')
    - character: optional Character instance to resolve common conditions

    Behavior: prefer condition-specific lists if present. Falls back to the
    generic 'dialogues' list. Returns an empty string if nothing found.
    """
    import random

    data = load_dialogues()
    ns = data.get(namespace, {}) if isinstance(data, dict) else {}
    node = ns.get(key, {}) if isinstance(ns, dict) else {}
    if not node:
        return ""
    # Resolve a few common conditions from the character context when not provided
    if condition is None and character is not None:
        # gold check
        if getattr(character, "gold", 0) <= 0 and "no_gold" in node:
            condition = "no_gold"
        # full health
        elif (
            getattr(character, "hp", 0) >= getattr(character, "max_hp", 0)
            and "full_health" in node
        ):
            condition = "full_health"
        # cursed (support both dicts and MagicItem objects)
        elif (
            getattr(character, "magic_items", None)
            and any(
                getattr(mi, "cursed", False)
                or (isinstance(mi, dict) and mi.get("cursed"))
                for mi in getattr(character, "magic_items", [])
            )
            and "cursed" in node
        ):
            condition = "cursed"
        # too drunk (uses a persistent buff flag) - only if the object has persistent_buffs
        elif (
            hasattr(character, "persistent_buffs")
            and getattr(character, "persistent_buffs", {}).get("debuff_drunk", 0) > 0
            and "too_drunk" in node
        ):
            condition = "too_drunk"
        # no companion
        elif (not getattr(character, "companion", None)) and "no_companion" in node:
            condition = "no_companion"

        # Charisma-based variants: prefer high/low charisma keys when available
        # Determine charisma safely for both Character objects and other entities
        try:
            if hasattr(character, "attributes") and isinstance(
                getattr(character, "attributes", None), dict
            ):
                cha = int(character.attributes.get("Charisma", 10))
            else:
                cha = int(getattr(character, "Charisma", 10))
        except Exception:
            cha = 10
        # user requested >15 or <5
        if cha > 15 and "charisma_high" in node:
            condition = "charisma_high"
        elif cha < 5 and "charisma_low" in node:
            condition = "charisma_low"

    # Prefer condition-specific list when available
    if condition and condition in node and node.get(condition):
        sub = node.get(condition)
        # If the condition resolves to a nested node (dict), try to pick
        # from its 'dialogues' list or any list field inside it.
        if isinstance(sub, dict):
            if sub.get("dialogues"):
                return random.choice(sub.get("dialogues"))
            for v in sub.values():
                if isinstance(v, list) and v:
                    return random.choice(v)
            # If it's a dict with no list to pick, fall through to empty string
            return ""
        # If it's a plain list, pick from it
        if isinstance(sub, list):
            return random.choice(sub)
        # Otherwise coerce to string
        return str(sub)

    # Fallback to generic dialogues
    if node.get("dialogues"):
        return random.choice(node.get("dialogues"))

    # As a last resort, try any list value present
    for v in node.values():
        if isinstance(v, list) and v:
            return random.choice(v)

    return ""


def get_npc_dialogue(
    namespace: str, key: str, condition: Optional[str] = None, character=None
) -> str:
    """Return a dialogue line prefixed by the NPC's name or role when available.

    Example: 'Roth: What'll it be?'

    This wraps get_dialogue() and looks up the 'name' or 'role' field in the
    corresponding dialogues.json node. If no dialogue is found, returns an empty
    string.
    """
    # Fetch the raw dialogue text
    text = get_dialogue(namespace, key, condition, character)
    if not text:
        return ""
    # Try to obtain the node's name/role from the dialogues JSON so we can prefix it
    data = load_dialogues()
    ns = data.get(namespace, {}) if isinstance(data, dict) else {}
    node = ns.get(key, {}) if isinstance(ns, dict) else {}

    # Avoid prefixing obvious headers/system nodes
    node_name = node.get("name") or ""
    node_role = node.get("role") or ""
    # If the caller passed a monster object, prefer that monster's name as the display prefix
    # (avoid using the player character's name as the speaker for town/NPC lines)
    if character is not None and namespace == "monster":
        try:
            char_name = getattr(character, "name", None)
        except Exception:
            char_name = None
        if char_name:
            return f"{char_name}: {text}"
    if (
        "header" in key.lower()
        or "header" in node_name.lower()
        or node_role == "System"
    ):
        return text

    # Load role -> NPC display name mapping from data/npc_names.json (if present)
    npc_map = _read_json("npc_names.json") or {}
    display_name = None
    # Prefer a human name only when it's not just a generic node title that
    # includes the role (e.g. 'Shopkeeper Sell'). If the node's name contains the
    # role string, prefer mapping by role so the actual NPC display name (from
    # data/npc_names.json) is used instead of the generic title.
    node_name = (node.get("name") or "").strip()
    if node_name and node_role and node_role.lower() in node_name.lower():
        # generic title — prefer role mapping
        node_name = ""
    # Prefer explicit name field first (only if it's not empty after the check above)
    if node_name:
        display_name = node_name
    # Next prefer mapping by role
    elif node_role and node_role in npc_map:
        display_name = npc_map.get(node_role)
    elif node_role:
        display_name = node_role

    if display_name:
        return f"{display_name}: {text}"
    return text
