import sys
from typing import List, Dict, Any

# Allow running as a standalone script from repo root
sys.path.append(".")

from game.engine import GameEngine
from game.entities import Companion


def last_menus(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [e for e in events if e.get("type") == "menu"]


def menu_has(events: List[Dict[str, Any]], action_id: str) -> bool:
    for m in last_menus(events):
        items = m.get("items", [])
        for it in items:
            if it.get("id") == action_id:
                return True
    return False


def drive_creation(engine: GameEngine):
    # Start new game and progress intro
    engine.start()
    engine.handle_action("main:new")
    engine.handle_action("intro:continue")
    engine.handle_action("intro:continue")
    # Submit a name
    engine.handle_action("prompt:submit", {"value": "Tester"})
    # Assign attributes quickly by always choosing index 0
    while engine.s.phase == "create_attrs" and engine.s.pending_attrs:
        engine.handle_action("attr:0")
    # Proceed through staged creation continues
    engine.handle_action("create:attrs_continue")
    engine.handle_action("create:hp_continue")
    engine.handle_action("create:summary_continue")
    assert engine.s.phase == "town", f"Expected to be in town, got {engine.s.phase}"


def test_inventory_gating(engine: GameEngine):
    engine.handle_action("town:inventory")
    ev = engine.handle_action("inv:unequip_weapon")
    assert menu_has(
        ev, "inv:continue"
    ), "Inventory: missing inv:continue after unequip weapon"


def test_levelup_gating(engine: GameEngine):
    c = engine.s.character
    c.unspent_stat_points = 1
    engine.handle_action("town:level")
    ev = engine.handle_action("level:Strength")
    assert menu_has(
        ev, "level:continue"
    ), "Level-up: missing level:continue after final allocation"
    engine.handle_action("level:continue")


def test_companion_heal_gating(engine: GameEngine):
    c = engine.s.character
    c.companion = Companion(
        name="Buddy", species="Wolf", hp=5, max_hp=10, armor_class=12, damage_die="1d4"
    )
    c.potions = 1  # ensure a heal can be performed
    engine.handle_action("town:companion")
    ev = engine.handle_action("comp:heal")
    assert menu_has(ev, "comp:continue"), "Companion: missing comp:continue after heal"
    engine.handle_action("comp:continue")


def test_quests_gating(engine: GameEngine):
    c = engine.s.character
    # Force capacity path (>=3 quests)
    c.side_quests = [{"desc": "A"}, {"desc": "B"}, {"desc": "C"}]
    engine.handle_action("town:quests")
    ev = engine.handle_action("quests:new")
    assert menu_has(
        ev, "quests:continue"
    ), "Quests: missing quests:continue after capacity message"
    engine.handle_action("quests:continue")


def test_dragon_victory(engine: GameEngine):
    # Simulate a combat state with a Dragon and trigger victory flow directly
    engine.s.phase = "combat"
    engine.s.current_room = {
        "description": "A vast, scorched cavern.",
        "gold_reward": 100,
        "has_chest": False,
        "monster": {
            "name": "Dragon",
            "hp": 0,
            "armor_class": 30,
            "damage_die": "8d7",
            "gold_reward": 250,
            "strength": 20,
            "dexterity": 18,
        },
    }
    room = engine.s.current_room
    mon = room["monster"]
    ev = engine._combat_victory(room, mon)
    assert menu_has(
        ev, "combat:dragon_victory_continue"
    ), "Dragon: missing final victory Continue gate"
    engine.handle_action("combat:dragon_victory_continue")
    assert (
        engine.s.phase == "main_menu"
    ), "After dragon victory, should return to main menu"


def main():
    engine = GameEngine()
    drive_creation(engine)
    test_inventory_gating(engine)
    test_levelup_gating(engine)
    test_companion_heal_gating(engine)
    test_quests_gating(engine)
    test_dragon_victory(engine)
    print("Smoke subphase tests: PASS")


if __name__ == "__main__":
    main()
