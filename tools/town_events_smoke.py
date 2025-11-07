from __future__ import annotations

# Minimal smoke test for event-driven town flows
# Runs a few actions with an emitter to verify event shapes and formatting.

import os, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from game.entities import Character, Weapon, Armor, MagicItem
from game.town import (
    eat_meal,
    tavern_drink,
    praying,
    weaponsmith,
    remove_curses,
    rest,
    train,
    gambling,
)


class Collector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        # Basic shape assertions
        assert isinstance(event, dict), "Event must be a dict"
        assert "type" in event, "Event requires a 'type'"
        self.events.append(event)


def make_char() -> Character:
    c = Character(name="Tester", clazz="Warrior", max_hp=30, gold=50)
    c.hp = 15
    # Some base attributes for variance
    c.attributes = {
        "Strength": 12,
        "Dexterity": 12,
        "Constitution": 12,
        "Intelligence": 10,
        "Wisdom": 12,
        "Charisma": 10,
        "Perception": 10,
    }
    return c


def run_smoke() -> None:
    c = make_char()
    emit = Collector()

    print("-- eat_meal --")
    eat_meal(c, emitter=emit)
    # Expect at least one dialogue and one state update
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "eat_meal must emit dialogue"
    assert any(
        e.get("type") == "state" for e in emit.events
    ), "eat_meal must emit state"
    emit.events.clear()

    print("-- tavern_drink --")
    tavern_drink(c, emitter=emit)
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "tavern_drink must emit dialogue"
    assert any(
        e.get("type") == "state" for e in emit.events
    ), "tavern_drink must emit state"
    emit.events.clear()

    print("-- praying --")
    praying(c, emitter=emit)
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "praying must emit dialogue"
    assert any(e.get("type") == "state" for e in emit.events), "praying must emit state"
    emit.events.clear()

    # Weaponsmith: simulate one damaged weapon and one damaged armor; choose first repair
    print("-- weaponsmith (repair first weapon) --")
    c2 = make_char()
    c2.gold = 100
    c2.weapons = [Weapon(name="Sword", damage_die="1d8", damaged=True)]
    c2.armors_owned = [Armor(name="Leather", armor_class=2, damaged=True)]
    # chooser to pick option 1
    chooser = lambda prompt: "1"
    start_gold = c2.gold
    weaponsmith(c2, emitter=emit, chooser=chooser)
    # Expect at least one dialogue and a state event reflecting gold decrease by 30
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "weaponsmith must emit dialogue"
    st = [e for e in emit.events if e.get("type") == "state"]
    assert (
        st and st[-1].get("gold") == start_gold - 30
    ), "weaponsmith must deduct 30g on repair"
    emit.events.clear()

    # Remove curses: add a cursed item and choose to remove it
    print("-- remove_curses (remove first) --")
    c3 = make_char()
    c3.gold = 100
    cursed = MagicItem(
        name="Ring of Pain",
        type="ring",
        effect="strength_penalty",
        cursed=True,
        penalty=2,
        description="Ouch",
    )
    c3.magic_items.append(cursed)
    start_gold = c3.gold
    chooser = lambda prompt: "1"
    remove_curses(c3, emitter=emit, chooser=chooser)
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "remove_curses must emit dialogue"
    st = [e for e in emit.events if e.get("type") == "state"]
    assert st and st[-1].get("gold") == start_gold - 20, "remove_curses must deduct 20g"
    # Item should be removed from inventory if helper succeeded
    assert not any(
        mi.name == "Ring of Pain" and mi.cursed for mi in c3.magic_items
    ), "cursed item should be removed or uncursed"
    emit.events.clear()

    # Rest: should emit dialogue and a state (HP or just state)
    print("-- rest --")
    c4 = make_char()
    rest(c4, emitter=emit)
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "rest must emit dialogue"
    assert any(e.get("type") == "state" for e in emit.events), "rest must emit state"
    emit.events.clear()

    # Train: choose first attribute, ensure gold deducted and attribute increased
    print("-- train (choose first attr) --")
    c5 = make_char()
    c5.gold = 1000
    attrs = list(c5.attributes.keys())
    first_attr = attrs[0]
    before_val = c5.attributes.get(first_attr, 10)
    chooser = lambda prompt: "1"
    start_gold = c5.gold
    train(c5, emitter=emit, chooser=chooser)
    # Gold should be reduced by 50 * (trained_times + 1) where trained_times starts at 0
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "train must emit dialogue"
    st = [e for e in emit.events if e.get("type") == "state"]
    assert (
        st and st[-1].get("gold") == start_gold - 50
    ), "train must deduct 50g on first training"
    assert (
        c5.attributes.get(first_attr, 0) == before_val + 1
    ), "attribute should increase by 1"

    # Gambling exact mode: choose D6, bet 10, pick 3, roller returns 3 -> win 40g
    print("-- gambling (exact, win) --")
    c6 = make_char()
    c6.gold = 100
    # chooser sequence: mode exact (1), die D6 (3), bet enter 10 then OK ("10","4"), pick number 3
    answers = iter(["1", "3", "10", "4", "3"])  # 1 exact, 3=D6, set 10, OK, pick 3
    chooser_seq = lambda prompt: next(answers)
    roller = lambda sides: 3
    start_gold = c6.gold
    gambling(c6, emitter=emit, chooser=chooser_seq, roller=roller)
    assert any(
        e.get("type") == "dialogue" for e in emit.events
    ), "gambling exact must emit dialogue"
    st = [e for e in emit.events if e.get("type") == "state"]
    # D6 multiplier int(6/1.5)=4; payout=10*4=40 -> gold = 140
    assert (
        st and st[-1].get("gold") == start_gold + 40
    ), "gambling exact win payout expected"
    emit.events.clear()

    # Gambling range mode: choose range 2 (6-10), bet 10, roller returns 7 -> win 30g
    print("-- gambling (range, win) --")
    c7 = make_char()
    c7.gold = 100
    answers = iter(["2", "2", "10", "4"])  # 2=range, choose range 2, set 10, OK
    chooser_seq = lambda prompt: next(answers)
    roller = lambda sides: 7
    start_gold = c7.gold
    gambling(c7, emitter=emit, chooser=chooser_seq, roller=roller)
    st = [e for e in emit.events if e.get("type") == "state"]
    assert (
        st and st[-1].get("gold") == start_gold + 30
    ), "gambling range win payout expected"

    # (Gambling tests omitted for now due to interactive loop complexities)

    print("Smoke OK: events captured and shaped correctly.")


if __name__ == "__main__":
    run_smoke()
