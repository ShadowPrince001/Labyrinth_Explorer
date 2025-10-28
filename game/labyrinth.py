import random
from dataclasses import dataclass
from typing import List, Optional

from .entities import Monster
from .data_loader import (
    load_monsters,
    load_magic_items,
    load_weapons,
    load_armors,
    load_potions,
    load_spells,
    get_dialogue,
)


@dataclass
class Room:
    description: str
    monster: Optional[Monster]
    gold_reward: int
    has_chest: bool = False
    chest_gold: int = 0
    chest_magic_item: Optional[str] = None
    room_id: Optional[int] = None


def _monster_by_name(name: str, depth: int) -> Optional[Monster]:
    from .data_loader import load_monsters

    data = load_monsters() or []
    entry = next(
        (m for m in data if (m.get("name") or "").lower() == name.lower()), None
    )
    if not entry:
        return None
    # Use base stats directly (no depth scaling)
    hp = int(entry.get("base_hp", 8))
    ac = int(entry.get("base_ac", 12))
    dex = int(entry.get("base_dex", 10))
    strength = int(entry.get("base_strength", 10))
    dmg_die = entry.get("damage_die", "1d6")
    return Monster(
        name=entry.get("name", name),
        hp=hp,
        armor_class=ac,
        damage_die=dmg_die,
        dexterity=dex,
        strength=strength,
    )


def generate_room(depth: int, character=None) -> Room:
    """Generate a room that always contains a monster chosen by wander_chance.

    Chest spawns and room descriptions are still varied, but a monster will be
    present in every room, weighted by the 'wander_chance' values in
    data/monsters.json.
    """
    # Chest chance independent of monsters
    has_chest = random.random() < 0.25
    chest_gold = 0
    chest_magic_item = None
    if has_chest:
        chest_gold = random.randint(10, 100)
        if random.random() < 0.5:
            chest_magic_item = generate_magic_item()

    # pick a thematic room id (1-6) for dialogue lookup
    room_id = random.randint(1, 6)

    # Always choose a monster using wander_chance weighting, but at depth 5 force Dragon
    monster = _monster_by_name("Dragon", depth) if depth == 5 else random_monster(depth)

    # Prefer a numbered room description; fall back to generic labyrinth entry text
    desc = (
        get_dialogue("labyrinth", "rooms", str(room_id), character)
        or get_dialogue("labyrinth", "room_entry", None, character)
        or random.choice(
            [
                "A damp chamber with flickering torchlight.",
                "Bones scatter the floor. A shadow moves.",
                "You hear a low growl from the darkness.",
                "Cold air spills from a cracked archway; something old breathes within.",
                "Scratched runes glow faintly on the walls—fresh claw marks score the stone.",
                "Candles gutter in a circle, recently lit. You are not alone.",
            ]
        )
    )
    gold = random.randint(5, 15) + depth * 2
    try:
        monster.gold_reward = gold
    except Exception:
        pass
    return Room(
        description=desc,
        monster=monster,
        gold_reward=gold,
        has_chest=has_chest,
        chest_gold=chest_gold,
        chest_magic_item=chest_magic_item,
        room_id=room_id,
    )


def random_monster(depth: int) -> Monster:
    data = load_monsters()
    if data:
        # Filter out Evil Necromancer for wandering monsters
        wandering_monsters = [m for m in data if m.get("name") != "Evil Necromancer"]

        # Use weighted selection based on wander_chance
        weights = [m.get("wander_chance", 0) for m in wandering_monsters]
        m = random.choices(wandering_monsters, weights=weights, k=1)[0]

        name = m.get("name", "Monster")
        # Use base stats directly (no depth scaling)
        hp = int(m.get("base_hp", 8))
        ac = int(m.get("base_ac", 12))
        dex = int(m.get("base_dex", 10))
        strength = int(m.get("base_strength", 10))
        dmg_die = m.get("damage_die", "1d6")
        return Monster(
            name=name,
            hp=hp,
            armor_class=ac,
            damage_die=dmg_die,
            dexterity=dex,
            strength=strength,
        )
    # fallback
    ac = 11 + min(depth // 2, 4)
    hp = 6 + depth * 2
    dmg_die = "1d6" if depth < 3 else "1d8"
    dex = max(8, 10 + depth // 2)
    strength = 10 + depth // 2
    name = random.choice(
        [
            "Goblin",
            "Skeleton",
            "Giant Rat",
            "Zombie",
            "Bandit",
        ]
    )
    return Monster(
        name=name,
        hp=hp,
        armor_class=ac,
        damage_die=dmg_die,
        dexterity=dex,
        strength=strength,
    )


def generate_magic_item() -> str:
    """Generate a random magic item name based on weighted chances."""
    # Build a candidate pool from several data sources. When JSON entries provide a
    # numeric 'chance' field, use it as a weight. Otherwise use conservative defaults.
    candidates = []  # list of tuples (name, weight)

    # Magic items (rings, artifacts, etc.)
    for item in load_magic_items() or []:
        name = item.get("name")
        if not name:
            continue
        # Use explicit 'chance' if present on magic item; otherwise use small default
        weight = int(item.get("chance", 3)) if item.get("chance") is not None else 3
        candidates.append((name, max(1, weight)))

    # Weapons (labyrinth-available)
    for w in load_weapons() or []:
        if w.get("availability", "shop") != "labyrinth":
            continue
        name = w.get("name")
        weight = int(w.get("chance", 1)) if w.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    # Armors (labyrinth-available)
    for a in load_armors() or []:
        if a.get("availability", "shop") != "labyrinth":
            continue
        name = a.get("name")
        weight = int(a.get("chance", 1)) if a.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    # Potions and spells: include as rare chest finds (no availability field)
    for p in load_potions() or []:
        name = p.get("name")
        weight = int(p.get("chance", 1)) if p.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    for s in load_spells() or []:
        # include only labyrinth-available spells (if availability is set)
        if s.get("availability") and s.get("availability") != "labyrinth":
            continue
        name = s.get("name")
        weight = int(s.get("chance", 1)) if s.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    if not candidates:
        return "Unknown Item"

    # Build weighted choice list
    names = [c[0] for c in candidates]
    weights = [c[1] for c in candidates]
    selected = random.choices(names, weights=weights, k=1)[0]
    return selected or "Unknown Item"
