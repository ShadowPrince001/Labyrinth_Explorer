from __future__ import annotations

# Smoke tests for event-driven shop flows (purchase and sell)
# Verifies dialogue/state events and basic gold/inventory deltas.

import os, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from game.entities import Character, Weapon, Armor
from game.shop import (
    browse_weapons,
    browse_armor,
    browse_potions,
    browse_spells,
    sell_items,
)


class Collector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        assert isinstance(event, dict)
        assert "type" in event
        self.events.append(event)


def make_char() -> Character:
    c = Character(name="Buyer", clazz="Rogue", max_hp=20, gold=200)
    c.hp = 20
    c.attributes = {
        "Strength": 10,
        "Dexterity": 12,
        "Constitution": 10,
        "Intelligence": 10,
        "Wisdom": 10,
        "Charisma": 12,
        "Perception": 10,
    }
    return c


def run_smoke() -> None:
    emit = Collector()

    # Prepare tiny shop datasets
    weapons_data = [
        {"name": "Dagger", "damage_die": "1d4", "price": 40},
    ]
    armors_data = [
        {"name": "Leather", "armor_class": 2, "price": 60},
    ]
    potions_data = [
        {"name": "Healing", "uses": 1, "cost": 20},
    ]
    spells_data = [
        {"name": "Firebolt", "uses": 1, "cost": 50},
    ]

    # 1) Buy a weapon (choose index 2 as menu starts at 2; 1 is Back)
    print("-- shop: buy weapon --")
    c1 = make_char()
    start_gold = c1.gold
    answers = iter(["2", "1"])  # select Dagger, then back
    chooser = lambda prompt: next(answers)
    browse_weapons(c1, weapons_data, emitter=emit, chooser=chooser)
    assert any(e["type"] == "dialogue" for e in emit.events)
    st = [e for e in emit.events if e["type"] == "state"]
    assert st and st[-1].get("gold") == start_gold - 40, "gold should decrease by price"
    assert any(w.name == "Dagger" for w in c1.weapons), "weapon added to inventory"
    emit.events.clear()

    # 2) Buy armor and auto-equip
    print("-- shop: buy armor --")
    c2 = make_char()
    start_gold = c2.gold
    answers = iter(["2", "1"])  # select Leather, then back
    chooser = lambda prompt: next(answers)
    browse_armor(c2, armors_data, emitter=emit, chooser=chooser)
    st = [e for e in emit.events if e["type"] == "state"]
    assert st and st[-1].get("gold") == start_gold - 60
    assert c2.armor and c2.armor.name == "Leather"
    emit.events.clear()

    # 3) Buy a potion (healing increments both potion_uses and legacy potions)
    print("-- shop: buy potion --")
    c3 = make_char()
    start_gold = c3.gold
    answers = iter(["2", "1"])  # Healing, then back
    chooser = lambda prompt: next(answers)
    browse_potions(c3, potions_data, emitter=emit, chooser=chooser)
    st = [e for e in emit.events if e["type"] == "state"]
    assert st and st[-1].get("gold") == start_gold - 20
    assert c3.potion_uses.get("Healing", 0) >= 1
    assert c3.potions >= 1
    emit.events.clear()

    # 4) Buy a spell
    print("-- shop: buy spell --")
    c4 = make_char()
    start_gold = c4.gold
    answers = iter(["2", "1"])  # Firebolt, then back
    chooser = lambda prompt: next(answers)
    browse_spells(c4, spells_data, emitter=emit, chooser=chooser)
    st = [e for e in emit.events if e["type"] == "state"]
    assert st and st[-1].get("gold") == start_gold - 50
    assert c4.spells.get("Firebolt", 0) >= 1
    emit.events.clear()

    # 5) Sell a weapon: add Dagger to inventory, then pick it and confirm
    print("-- shop: sell weapon --")
    c5 = make_char()
    c5.weapons.append(Weapon(name="Dagger", damage_die="1d4"))
    # chooser: menu '2' (weapon), then confirm 'y'
    answers = iter(["2", "y"])  # Back is 1, item is 2
    chooser = lambda prompt: next(answers)
    before_gold = c5.gold
    # Sanity: inventory and shop dataset match
    # Deterministic appraisal: d20=15, CHA=12 -> percent=0.675, appraised=27
    sell_items(
        c5,
        weapons_data,
        armors_data,
        potions_data,
        emitter=emit,
        chooser=chooser,
        roller=lambda: 15,
    )
    assert c5.gold == before_gold + 27, "gold should increase by appraised amount"
    assert not any(w.name == "Dagger" for w in c5.weapons), "weapon removed after sale"
    emit.events.clear()

    # 6) Selling equipped weapon should be refused
    print("-- shop: sell equipped weapon (refuse) --")
    c6 = make_char()
    c6.weapons = [Weapon(name="Dagger", damage_die="1d4")]
    c6.equipped_weapon_index = 0
    answers = iter(["2", "1"])  # choose the only weapon then Back after refusal
    chooser = lambda prompt: next(answers)
    start_gold = c6.gold
    sell_items(
        c6,
        weapons_data,
        armors_data,
        potions_data,
        emitter=emit,
        chooser=chooser,
        roller=lambda: 10,
    )
    assert c6.gold == start_gold, "equipped item cannot be sold"
    assert any(w.name == "Dagger" for w in c6.weapons), "weapon should remain"
    assert any(
        (e.get("type") == "dialogue" and "equipped" in e.get("text", "").lower())
        for e in emit.events
    ), "should emit equipped refusal message"
    emit.events.clear()

    # 7) Selling damaged items should be refused
    print("-- shop: sell damaged weapon (refuse) --")
    c7 = make_char()
    c7.weapons = [Weapon(name="Dagger", damage_die="1d4", damaged=True)]
    answers = iter(["2", "1"])  # damaged entry then Back
    chooser = lambda prompt: next(answers)
    start_gold = c7.gold
    sell_items(
        c7, weapons_data, armors_data, potions_data, emitter=emit, chooser=chooser
    )
    assert c7.gold == start_gold, "damaged item should not be sellable"
    assert any(
        (e.get("type") == "dialogue" and "damaged" in e.get("text", "").lower())
        for e in emit.events
    ), "should mention damaged refusal"
    emit.events.clear()

    # 8) Selling potions should decrease uses and increase gold by appraised
    print("-- shop: sell potion use --")
    c8 = make_char()
    c8.potion_uses["Healing"] = 2
    answers = iter(["2", "y", "1"])  # select Healing potion, confirm, then Back
    chooser = lambda prompt: next(answers)
    start_gold = c8.gold
    sell_items(
        c8,
        weapons_data,
        armors_data,
        potions_data,
        emitter=emit,
        chooser=chooser,
        roller=lambda: 12,
    )
    # With CHA 12 → (12+12)*.025≈0.6000000000000001, ceil(20*0.600000...)=13
    # Gold delta after sale
    assert c8.gold == start_gold + 13
    assert c8.potion_uses.get("Healing", 0) == 1
    emit.events.clear()

    # 9) Invalid input branch: non-digit then valid then cancel
    print("-- shop: invalid menu input then valid --")
    c9 = make_char()
    c9.weapons.append(Weapon(name="Dagger", damage_die="1d4"))
    answers = iter(["x", "2", "n", "1"])  # invalid, then valid select, cancel, Back
    chooser = lambda prompt: next(answers)
    start_gold = c9.gold
    sell_items(
        c9,
        weapons_data,
        armors_data,
        potions_data,
        emitter=emit,
        chooser=chooser,
        roller=lambda: 10,
    )
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "should emit a dialogue on invalid selection"
    assert c9.gold == start_gold

    print("Shop smoke OK: events and deltas look good.")


if __name__ == "__main__":
    run_smoke()
