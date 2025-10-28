"""
DEPRECATED MODULE
-----------------
This module is no longer used. Importing it will raise to prevent accidental use.
Use game.labyrinth instead.
"""

raise ImportError("game.dungeon is deprecated. Use game.labyrinth instead.")

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


def generate_room(depth: int, character=None) -> Room:
    """Generate a room. If character provided, prefer dialogue-based descriptions."""
    event_roll = random.random()

    # Check for chest spawn (25% chance)
    has_chest = random.random() < 0.25
    chest_gold = 0
    chest_magic_item = None

    if has_chest:
        # Chest always has gold (10-100)
        chest_gold = random.randint(10, 100)

        # 50% chance for magic item
        if random.random() < 0.5:
            chest_magic_item = generate_magic_item()

    if event_roll < 0.6:
        monster = random_monster(depth)
        # Prefer dialogue-driven room entry descriptions when available
        desc = get_dialogue("dungeon", "room_entry", None, character) or random.choice(
            [
                "A damp chamber with flickering torchlight.",
                "Bones scatter the floor. A shadow moves.",
                "You hear a low growl from the darkness.",
                "Cold air spills from a cracked archway; something old breathes within.",
                "Scratched runes glow faintly on the walls—fresh claw marks score the stone.",
                "Candles gutter in a circle, recently lit. You are not alone.",
            ]
        )
        gold = random.randint(5, 10) + depth * 2
        monster.gold_reward = gold
        return Room(
            description=desc,
            monster=monster,
            gold_reward=gold,
            has_chest=has_chest,
            chest_gold=chest_gold,
            chest_magic_item=chest_magic_item,
        )
    elif event_roll < 0.85:
        desc = get_dialogue(
            "dungeon", "examine_room", None, character
        ) or random.choice(
            [
                "An empty corridor lined with ancient carvings.",
                "A collapsed hallway. You squeeze through.",
                "Dust hangs in the air; distant water drips in a steady rhythm.",
                "A shrine long-abandoned: cracked statue, scattered offerings.",
            ]
        )
        return Room(
            description=desc,
            monster=None,
            gold_reward=0,
            has_chest=has_chest,
            chest_gold=chest_gold,
            chest_magic_item=chest_magic_item,
        )
    else:
        # small loot alcove - reuse dungeon room_entry fallback or a short chestty description
        desc = get_dialogue("dungeon", "room_entry", None, character) or random.choice(
            [
                "A glimmer of coins in a dusty alcove.",
                "Behind a loose brick, a small cache glints.",
                "A toppled chest, its lock broken ages ago.",
            ]
        )
        gold = random.randint(10, 20) + depth * 3
        return Room(
            description=desc,
            monster=None,
            gold_reward=gold,
            has_chest=has_chest,
            chest_gold=chest_gold,
            chest_magic_item=chest_magic_item,
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
        # Scale stats by depth (monsters get stronger at deeper levels)
        base_hp = int(m.get("base_hp", 8))
        base_ac = int(m.get("base_ac", 12))
        base_dex = int(m.get("base_dex", 10))
        base_strength = int(m.get("base_strength", 10))

        # Scaling: +2 HP, +1 AC per depth level
        hp = base_hp + (depth - 1) * 2
        ac = base_ac + (depth - 1)
        dex = base_dex + (depth - 1)
        strength = base_strength + (depth - 1)

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
    # Same approach as labyrinth: collect candidates from several sources
    candidates = []

    for item in load_magic_items() or []:
        name = item.get("name")
        if not name:
            continue
        weight = int(item.get("chance", 3)) if item.get("chance") is not None else 3
    candidates.append((name, max(1, weight)))

    for w in load_weapons() or []:
        if w.get("availability", "shop") != "labyrinth":
            continue
        name = w.get("name")
        weight = int(w.get("chance", 1)) if w.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    for a in load_armors() or []:
        if a.get("availability", "shop") != "labyrinth":
            continue
        name = a.get("name")
        weight = int(a.get("chance", 1)) if a.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    for p in load_potions() or []:
        name = p.get("name")
        weight = int(p.get("chance", 1)) if p.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    for s in load_spells() or []:
        if s.get("availability") and s.get("availability") not in (
            "dungeon",
            "labyrinth",
        ):
            continue
        name = s.get("name")
        weight = int(s.get("chance", 1)) if s.get("chance") is not None else 1
        candidates.append((name, max(1, weight)))

    if not candidates:
        return "Unknown Item"

    names = [c[0] for c in candidates]
    weights = [c[1] for c in candidates]
    return random.choices(names, weights=weights, k=1)[0]
