"""Tests for charm mechanics and progressive depth rewards in the web engine.

This file creates a GameEngine instance and drives internal methods to validate:
- One charm attempt per combat is enforced and resets on new combat
- Charm success threshold scales with monster difficulty
- Victory rewards use progressive depth multiplier (1.0, 1.5, 2.0, ...)
- Charm rewards are 25% of depth-scaled rewards
"""

import sys, os
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.engine import GameEngine
from game.entities import Character


def make_char(name="Tester", cha=10, dex=12):
    c = Character(name=name, clazz="Adventurer", max_hp=30, gold=0)
    c.hp = 30
    c.attributes = {
        "Strength": 10,
        "Dexterity": dex,
        "Constitution": 10,
        "Intelligence": 10,
        "Wisdom": 10,
        "Charisma": cha,
        "Perception": 10,
    }
    return c


def extract_texts(events: List[dict], etype="combat_update") -> List[str]:
    return [e.get("text", "") for e in events if e.get("type") == etype]


def test_single_charm_attempt_enforced():
    eng = GameEngine()
    eng.s.character = make_char(cha=12)
    eng.s.phase = "combat"
    eng.s.subphase = "player_menu"
    # Custom monster not in data for deterministic rewards
    mon = {
        "name": "UnitTestMonster",
        "hp": 10,
        "armor_class": 10,
        "damage_die": "1d4",
        "gold_reward": 50,
        "dexterity": 10,
    }
    eng.s.current_room = {"monster": mon}
    # Prepare combat container
    eng.s.combat = {"buffs": {}, "enemy": {"debuffs": {}}, "turn": "player"}
    # First attempt
    ev1 = eng._combat_charm(None)
    texts1 = "\n".join(extract_texts(ev1))
    assert "attempt to charm" in texts1.lower()
    # Second attempt in same combat should be blocked
    ev2 = eng._combat_charm(None)
    texts2 = "\n".join(extract_texts(ev2))
    assert "already attempted" in texts2.lower(), texts2


def test_progressive_depth_multiplier_victory():
    eng = GameEngine()
    eng.s.character = make_char()
    eng.s.depth = 5  # multiplier = 1 + 0.5*(5-1) = 3.0
    mon = {
        "name": "UnitTestMonster",
        "hp": 0,
        "armor_class": 10,
        "damage_die": "1d4",
        "gold_reward": 100,
    }
    room = {"monster": mon, "gold_reward": 0}
    # Baseline values
    start_xp, start_gold = eng.s.character.xp, eng.s.character.gold
    ev = eng._combat_victory(room, mon)
    # Expect XP = 10 * 3 = 30 (base_xp fallback), gold = 100 * 3 = 300
    assert (
        eng.s.character.xp - start_xp == 30
    ), f"XP mismatch: got {eng.s.character.xp - start_xp}"
    assert (
        eng.s.character.gold - start_gold == 300
    ), f"Gold mismatch: got {eng.s.character.gold - start_gold}"


def test_charm_rewards_quarter_of_depth_scaled():
    eng = GameEngine()
    # Make success very likely
    eng.s.character = make_char(cha=50)
    eng.s.depth = 5  # multiplier = 3.0
    mon = {
        "name": "UnitTestMonster",
        "hp": 10,
        "armor_class": 10,
        "damage_die": "1d4",
        "gold_reward": 100,
        "dexterity": 10,
    }
    eng.s.current_room = {"monster": mon, "gold_reward": 0}
    eng.s.phase = "combat"
    eng.s.subphase = "player_menu"
    eng.s.combat = {"buffs": {}, "enemy": {"debuffs": {}}, "turn": "player"}
    start_xp, start_gold = eng.s.character.xp, eng.s.character.gold
    ev = eng._combat_charm(None)
    # Expect quarter: XP = int(10 * 3.0 * 0.25) = 7, gold = int(100 * 3.0 * 0.25) = 75
    dxp = eng.s.character.xp - start_xp
    dgold = eng.s.character.gold - start_gold
    assert dxp == 7, f"Charm XP mismatch: {dxp}"
    assert dgold == 75, f"Charm gold mismatch: {dgold}"


def test_charm_threshold_scales_with_difficulty():
    eng = GameEngine()
    eng.s.character = make_char(cha=10)
    eng.s.phase = "combat"
    eng.s.subphase = "player_menu"
    # Difficulty fallback (not in data) -> diff=1
    mon_easy = {
        "name": "UnitTestMonster",
        "hp": 10,
        "armor_class": 10,
        "damage_die": "1d4",
        "gold_reward": 0,
        "dexterity": 10,
    }
    eng.s.current_room = {"monster": mon_easy}
    eng.s.combat = {"buffs": {}, "enemy": {"debuffs": {}}, "turn": "player"}
    ev_easy = eng._combat_charm(None)
    t_easy = "\n".join(extract_texts(ev_easy))
    # Now a known hard monster from data: Death Knight (difficulty ~10)
    eng.s.combat = {"buffs": {}, "enemy": {"debuffs": {}}, "turn": "player"}
    mon_hard = {
        "name": "Death Knight",
        "hp": 100,
        "armor_class": 28,
        "damage_die": "8d6",
        "dexterity": 16,
    }
    eng.s.current_room = {"monster": mon_hard}
    ev_hard = eng._combat_charm(None)
    t_hard = "\n".join(extract_texts(ev_hard))
    import re

    m1 = re.search(r"need >(\d+)", t_easy)
    m2 = re.search(r"need >(\d+)", t_hard)
    assert m1 and m2, f"Could not parse thresholds: easy='{t_easy}', hard='{t_hard}'"
    th_easy, th_hard = int(m1.group(1)), int(m2.group(1))
    assert (
        th_hard > th_easy
    ), f"Hard threshold ({th_hard}) should be greater than easy ({th_easy})"


if __name__ == "__main__":
    try:
        test_single_charm_attempt_enforced()
        print("PASS single_charm_attempt_enforced")
        test_progressive_depth_multiplier_victory()
        print("PASS progressive_depth_multiplier_victory")
        test_charm_rewards_quarter_of_depth_scaled()
        print("PASS charm_rewards_quarter_of_depth_scaled")
        test_charm_threshold_scales_with_difficulty()
        print("PASS charm_threshold_scales_with_difficulty")
        print("All charm and rewards tests passed.")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
