from __future__ import annotations

import random
from typing import Optional

from .dice import roll_damage
import math
from .entities import Character
from .data_loader import load_traps, get_dialogue


def ability_bonus(attrs: dict, key: str) -> int:
    """Return rounded-up half of the ability for checks (e.g., Dex/2 ceil).

    This brings trap saves in line with new mechanics.
    """
    val = int(attrs.get(key, 10))
    return math.ceil(val / 2)


def apply_effect(character: Character, effect: dict) -> None:
    typ = effect.get("type")
    if typ == "gold_dust":
        lose = min(character.gold, int(effect.get("amount", 50)))
        character.gold -= lose
        msg = get_dialogue("traps", "gold_dust", None, character)
        print(
            msg.format(amount=lose)
            if msg
            else f"Some of your gold turns to dust! You lose {lose} gold."
        )
    elif typ == "poison":
        dur = int(effect.get("duration", 2))
        character.persistent_buffs["debuff_poison"] = max(
            character.persistent_buffs.get("debuff_poison", 0), dur
        )
        msg = get_dialogue("traps", "poisoned", None, character)
        print(msg.format(duration=dur) if msg else "You have been poisoned!")
    elif typ == "rust_weapon":
        # Old rust trap: it no longer permanently damages equipment.
        # Keep flavor text but do not set persistent damage flags.
        if character.weapons:
            w = character.weapons[0]
            msg = get_dialogue("traps", "rust_weapon", None, character)
            print(
                msg.format(name=w.name)
                if msg
                else f"Your {w.name} is splattered with corrosive dust, but it holds for now."
            )
    elif typ == "dex_down":
        character.attributes["Dexterity"] = max(
            1, character.attributes.get("Dexterity", 10) - int(effect.get("amount", 1))
        )
        msg = get_dialogue("traps", "dex_down", None, character)
        print(msg or "Your dexterity is sapped by the mist.")


def resolve_trap(character: Character, trap: dict) -> None:
    name = trap.get("name", "Trap")
    dc = int(trap.get("dc", 10))
    dmg_die = trap.get("damage", "0d0")
    msg = get_dialogue("traps", "trap_alert", None, character)
    print(msg.format(name=name) if msg else f"Trap! {name}!")
    # New mechanics: 5d4 + Dex/2(ceil)
    roll = roll_damage("5d4") + ability_bonus(character.attributes, "Dexterity")
    msg = get_dialogue("traps", "dodge_roll", None, character)
    print(msg.format(roll=roll, dc=dc) if msg else f"Dodge roll: {roll} vs DC {dc}")
    if roll >= dc:
        msg = get_dialogue("traps", "avoid_trap", None, character)
        print(msg or "You avoid the trap!")
        return
    dmg = max(0, roll_damage(dmg_die))
    if dmg > 0:
        character.hp -= dmg
        msg = get_dialogue("traps", "trap_damage", None, character)
        print(
            msg.format(dmg=dmg, hp=max(character.hp, 0))
            if msg
            else f"You are hit for {dmg} damage. HP: {max(character.hp, 0)}"
        )
    for eff in trap.get("effects", []):
        # Effect may have a chance
        chance = eff.get("chance")
        if chance is not None and random.random() > float(chance):
            continue
        apply_effect(character, eff)


def random_room_trap() -> Optional[dict]:
    traps = load_traps()
    if not traps:
        return None
    if random.random() < 0.2:
        return random.choice(traps)
    return None


# --- Event-friendly helpers ---
def resolve_trap_events(character: Character, trap: dict) -> list[str]:
    """Resolve a trap but return dialogue lines instead of printing.

    Applies effects to character like resolve_trap().
    """
    lines: list[str] = []
    name = trap.get("name", "Trap")
    dc = int(trap.get("dc", 10))
    dmg_die = trap.get("damage", "0d0")
    msg = get_dialogue("traps", "trap_alert", None, character)
    lines.append((msg.format(name=name) if msg else f"Trap! {name}!"))
    # New mechanics: 5d4 + Dex/2(ceil)
    roll = roll_damage("5d4") + ability_bonus(character.attributes, "Dexterity")
    msg = get_dialogue("traps", "dodge_roll", None, character)
    lines.append(
        (msg.format(roll=roll, dc=dc) if msg else f"Dodge roll: {roll} vs DC {dc}")
    )
    if roll >= dc:
        msg = get_dialogue("traps", "avoid_trap", None, character)
        lines.append(msg or "You avoid the trap!")
        return lines
    dmg = max(0, roll_damage(dmg_die))
    if dmg > 0:
        character.hp -= dmg
        msg = get_dialogue("traps", "trap_damage", None, character)
        lines.append(
            msg.format(dmg=dmg, hp=max(character.hp, 0))
            if msg
            else f"You are hit for {dmg} damage. HP: {max(character.hp, 0)}"
        )
    for eff in trap.get("effects", []):
        chance = eff.get("chance")
        if chance is not None and random.random() > float(chance):
            continue
        # Intercept prints by capturing to a temp list then extend
        before_hp = character.hp
        before_gold = character.gold
        apply_effect(character, eff)
        # Attempt to mirror the print messages for effects using dialogue again
        typ = eff.get("type")
        if typ == "gold_dust":
            lose = min(before_gold, int(eff.get("amount", 50)))
            msg = get_dialogue("traps", "gold_dust", None, character)
            lines.append(
                msg.format(amount=lose)
                if msg
                else f"Some of your gold turns to dust! You lose {lose} gold."
            )
        elif typ == "poison":
            dur = int(eff.get("duration", 2))
            msg = get_dialogue("traps", "poisoned", None, character)
            lines.append(msg.format(duration=dur) if msg else "You have been poisoned!")
        elif typ == "rust_weapon":
            if character.weapons:
                w = character.weapons[0]
                msg = get_dialogue("traps", "rust_weapon", None, character)
                lines.append(
                    msg.format(name=w.name)
                    if msg
                    else f"Your {w.name} is splattered with corrosive dust, but it holds for now."
                )
        elif typ == "dex_down":
            msg = get_dialogue("traps", "dex_down", None, character)
            lines.append(msg or "Your dexterity is sapped by the mist.")
    return lines
