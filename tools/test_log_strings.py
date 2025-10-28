import io
import random
import sys
import os
from contextlib import redirect_stdout

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import builtins
from game.entities import Character, Weapon, Monster
from game.combat import initiative_order, player_turn, monster_turn


def make_basic_char():
    c = Character(
        name="Tester",
        clazz="Fighter",
        max_hp=30,
        gold=100,
    )
    c.hp = 30
    c.attributes = {
        "Strength": 12,
        "Dexterity": 11,
        "Constitution": 12,
        "Intelligence": 10,
        "Wisdom": 10,
        "Charisma": 10,
        "Perception": 10,
    }
    c.weapons.append(Weapon(name="Dagger", damage_die="1d4"))
    return c


def make_basic_mon():
    return Monster(
        name="Goblin",
        hp=15,
        armor_class=12,
        damage_die="1d4",
        dexterity=10,
        strength=10,
    )


def test_initiative_format():
    random.seed(1)
    c = make_basic_char()
    m = make_basic_mon()
    buf = io.StringIO()
    with redirect_stdout(buf):
        initiative_order(c, m)
    out = buf.getvalue()
    assert "Initiative - You:" in out and "(roll +" in out, out


def test_player_attack_line():
    random.seed(2)
    c = make_basic_char()
    m = make_basic_mon()

    # Mock input sequence: "1" to Attack, "2" to aim middle
    inputs = iter(["1", "2"])  # attack, aim middle
    orig_input = builtins.input
    builtins.input = lambda prompt=None: next(inputs)
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            # We don't care about the return value; we just want the log
            player_turn(c, m, buffs={}, enemy_debuffs={})
        out = buf.getvalue()
        assert "You aim" in out and "roll:" in out and "vs AC" in out, out
    finally:
        builtins.input = orig_input


def test_monster_attack_line():
    random.seed(3)
    c = make_basic_char()
    m = make_basic_mon()

    # Mock input for choose_defend_zone: "2" (middle)
    inputs = iter(["2"])  # defend middle
    orig_input = builtins.input
    builtins.input = lambda prompt=None: next(inputs)
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            monster_turn(c, m, buffs={}, enemy_debuffs={})
        out = buf.getvalue()
        assert m.hp >= 0, "Monster HP should remain non-negative"
        assert "attacks" in out and "roll" in out and "Strength/2" in out, out
    finally:
        builtins.input = orig_input


if __name__ == "__main__":
    # Run tests and print a compact summary
    tests = [
        ("initiative_format", test_initiative_format),
        ("player_attack_line", test_player_attack_line),
        ("monster_attack_line", test_monster_attack_line),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failures += 1
            print(f"FAIL {name}: {e}")
    if failures:
        sys.exit(1)
    print("All log string tests passed.")
