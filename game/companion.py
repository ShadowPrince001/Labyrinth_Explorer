from __future__ import annotations

import random
from dataclasses import dataclass

from .dice import roll_damage
from .entities import Character, Companion, Monster
from .data_loader import get_dialogue


SUMMON_TABLE = [
    # High tier (needs 16+)
    {
        "species": "Lion",
        "damage_die": "4d6",
        "ac_range": (12, 14),
        "str_range": (12, 15),
        "hp_range": (50, 75),
        "min_roll": 16,
    },
    {
        "species": "Bear",
        "damage_die": "4d6",
        "ac_range": (12, 14),
        "str_range": (12, 15),
        "hp_range": (50, 75),
        "min_roll": 16,
    },
    {
        "species": "Tiger",
        "damage_die": "4d6",
        "ac_range": (12, 14),
        "str_range": (12, 15),
        "hp_range": (50, 75),
        "min_roll": 16,
    },
    # Mid tier (12-15)
    {
        "species": "Wolf",
        "damage_die": "3d6",
        "ac_range": (10, 12),
        "str_range": (10, 12),
        "hp_range": (30, 50),
        "min_roll": 12,
    },
    {
        "species": "Panther",
        "damage_die": "3d6",
        "ac_range": (10, 12),
        "str_range": (10, 12),
        "hp_range": (30, 50),
        "min_roll": 12,
    },
    {
        "species": "Eagle",
        "damage_die": "3d6",
        "ac_range": (10, 12),
        "str_range": (10, 12),
        "hp_range": (30, 50),
        "min_roll": 12,
    },
    # Low tier (8-11)
    {
        "species": "Dog",
        "damage_die": "2d6",
        "ac_range": (8, 10),
        "str_range": (8, 10),
        "hp_range": (15, 30),
        "min_roll": 8,
    },
    {
        "species": "Cat",
        "damage_die": "2d6",
        "ac_range": (8, 10),
        "str_range": (8, 10),
        "hp_range": (15, 30),
        "min_roll": 8,
    },
    {
        "species": "Owl",
        "damage_die": "2d6",
        "ac_range": (8, 10),
        "str_range": (8, 10),
        "hp_range": (15, 30),
        "min_roll": 8,
    },
]


def roll_range(lo: int, hi: int) -> int:
    return random.randint(lo, hi)


def create_companion_from_entry(entry: dict) -> Companion:
    ac = roll_range(*entry["ac_range"])
    hp = roll_range(*entry["hp_range"])
    # Roll a strength value from the entry's str_range if present

    str_val = roll_range(*entry["str_range"])

    return Companion(
        name=entry["species"],
        species=entry["species"],
        hp=hp,
        max_hp=hp,
        armor_class=ac,
        damage_die=entry["damage_die"],
        strength=str_val,
    )


def summon_companion(character: Character, roll_value: int) -> bool:
    """Summon a companion using roll_value modified by Intelligence and Charisma.

    Behavior changes:
    - The summoning final roll is: final_roll = roll_value + int_mod + cha_mod, where
      stat_mod = (stat - 10) // 2 (D&D-style modifier).
    - If the final_roll is below any table entry (no eligible entries), the summoning
      fails (no fallback familiar). This replaces the old fallback behaviour.
    """
    if character.companion is not None:
        print(
            get_dialogue("companion", "summon_already", None, character)
            or "You already have a companion."
        )
        return False

    # Compute attribute modifiers (fall back to 10 if attribute not present)
    int_stat = character.attributes.get(
        "Intelligence", character.attributes.get("Int", 10)
    )
    cha_stat = character.attributes.get("Charisma", character.attributes.get("Cha", 10))
    int_mod = (int_stat - 10) // 2
    cha_mod = (cha_stat - 10) // 2
    bonus = int_mod + cha_mod
    final_roll = roll_value + bonus

    # Inform player of the roll and bonus (use dialogue if available)
    try:
        print(
            get_dialogue("companion", "summon_roll", None, character)
            or f"You rolled {roll_value}. Bonus from Int+Cha: {bonus}. Final roll: {final_roll}."
        )
    except Exception:
        print(
            f"You rolled {roll_value}. Bonus from Int+Cha: {bonus}. Final roll: {final_roll}."
        )

    # Filter entries that meet the min_roll threshold using the final roll
    eligible = [e for e in SUMMON_TABLE if final_roll >= e["min_roll"]]
    if not eligible:
        # Low final roll -> summoning fails (no familiar fallback)
        print(
            get_dialogue("companion", "summon_fail", None, character)
            or "The summoning fails; no creature answers your call."
        )
        return False

    # Prefer highest min_roll not exceeding final_roll
    best_min = max(e["min_roll"] for e in eligible)
    candidates = [e for e in eligible if e["min_roll"] == best_min]
    entry = random.choice(candidates)
    character.companion = create_companion_from_entry(entry)
    # Use dialogue template if available
    joined = get_dialogue("companion", "summon_success", None, character)
    if joined:
        try:
            print(
                joined.format(
                    species=character.companion.species, name=character.companion.name
                )
            )
        except Exception:
            print(f"A {character.companion.species} joins you!")
    else:
        print(f"A {character.companion.species} joins you!")
    return True


def companion_turn(character: Character, monster: Monster) -> None:
    comp = character.companion
    if not comp or comp.hp <= 0:
        return
    # Companion attack: roll damage and add companion strength to determine if the
    # attack overcomes the monster's AC. If (damage_roll + strength) > monster AC,
    # the attack hits and deals the damage_roll amount.
    damage_roll = max(1, roll_damage(comp.damage_die))
    attack_value = random.randint(1, 20) + getattr(comp, "strength", 0)
    if attack_value > monster.armor_class:
        monster.hp -= damage_roll
        hp_text = max(monster.hp, 0)
        attack_line = get_dialogue("companion", "attack_hit", None, character)
        if attack_line:
            try:
                print(attack_line.format(comp=comp.name, dmg=damage_roll, hp=hp_text))
            except Exception:
                print(
                    f"{comp.name} attacks for {damage_roll} damage. Monster HP: {hp_text}"
                )
        else:
            print(
                f"{comp.name} attacks for {damage_roll} damage. Monster HP: {hp_text}"
            )
    else:
        miss_line = get_dialogue("companion", "attack_miss", None, character)
        print(miss_line.format(comp=comp.name) if miss_line else f"{comp.name} misses.")


def name_companion(character: Character, new_name: str) -> None:
    if character.companion:
        character.companion.name = new_name
        name_line = get_dialogue("companion", "name_success", None, character)
        print(
            name_line.format(name=new_name)
            if name_line
            else f"Your companion is now named {new_name}."
        )
    else:
        print(
            get_dialogue("companion", "name_no_companion", None, character)
            or "You have no companion to name."
        )


def heal_companion(character: Character) -> None:
    if not character.companion:
        print(
            get_dialogue("companion", "heal_no_companion", None, character)
            or "You have no companion."
        )
        return
    if character.potions <= 0 and character.potion_uses.get("Healing", 0) <= 0:
        print(
            get_dialogue("companion", "heal_no_potions", None, character)
            or "You have no healing potions."
        )
        return
    # consume legacy or new healing
    if character.potions > 0:
        character.potions -= 1
    else:
        character.potion_uses["Healing"] -= 1
    heal = max(1, roll_damage("2d4"))
    character.companion.hp = min(
        character.companion.max_hp, character.companion.hp + heal
    )
    heal_line = get_dialogue("companion", "heal_success", None, character)
    if heal_line:
        try:
            print(heal_line.format(heal=heal))
        except Exception:
            print(f"You heal your companion for {heal} HP.")
    else:
        print(f"You heal your companion for {heal} HP.")
