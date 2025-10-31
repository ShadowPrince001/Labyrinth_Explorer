"""Test script for difficulty selection system."""

import sys, os

root = os.path.dirname(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

from game.engine import GameEngine


def test_difficulty_system():
    print("=" * 60)
    print("Testing Difficulty Selection System")
    print("=" * 60)

    # Test 1: Check difficulty configuration exists
    print("\n[Test 1] Checking DIFFICULTY_CONFIG...")
    engine = GameEngine()
    assert hasattr(engine, "DIFFICULTY_CONFIG"), "DIFFICULTY_CONFIG not found!"
    assert "easy" in engine.DIFFICULTY_CONFIG, "Easy difficulty missing!"
    assert "normal" in engine.DIFFICULTY_CONFIG, "Normal difficulty missing!"
    assert "hard" in engine.DIFFICULTY_CONFIG, "Hard difficulty missing!"
    print("✓ All three difficulties configured")

    # Test 2: Verify dice formulas
    print("\n[Test 2] Verifying dice formulas...")
    assert (
        engine.DIFFICULTY_CONFIG["easy"]["dice"] == "6d5"
    ), f"Easy dice wrong: {engine.DIFFICULTY_CONFIG['easy']['dice']}"
    assert (
        engine.DIFFICULTY_CONFIG["normal"]["dice"] == "5d5"
    ), f"Normal dice wrong: {engine.DIFFICULTY_CONFIG['normal']['dice']}"
    assert (
        engine.DIFFICULTY_CONFIG["hard"]["dice"] == "4d5"
    ), f"Hard dice wrong: {engine.DIFFICULTY_CONFIG['hard']['dice']}"
    print("✓ Easy: 6d5, Normal: 5d5, Hard: 4d5")

    # Test 3: Check state field
    print("\n[Test 3] Checking difficulty state field...")
    assert hasattr(engine.s, "difficulty"), "Difficulty field missing from state!"
    assert (
        engine.s.difficulty == "normal"
    ), f"Default difficulty should be 'normal', got '{engine.s.difficulty}'"
    print("✓ Difficulty field exists with default 'normal'")

    # Test 4: Test helper method
    print("\n[Test 4] Testing _get_stat_roll_dice() method...")
    assert hasattr(engine, "_get_stat_roll_dice"), "Helper method missing!"

    # Test each difficulty
    engine.s.difficulty = "easy"
    assert (
        engine._get_stat_roll_dice() == "6d5"
    ), f"Easy dice returned wrong: {engine._get_stat_roll_dice()}"

    engine.s.difficulty = "normal"
    assert (
        engine._get_stat_roll_dice() == "5d5"
    ), f"Normal dice returned wrong: {engine._get_stat_roll_dice()}"

    engine.s.difficulty = "hard"
    assert (
        engine._get_stat_roll_dice() == "4d5"
    ), f"Hard dice returned wrong: {engine._get_stat_roll_dice()}"

    print("✓ Helper method returns correct dice for all difficulties")

    # Test 5: Test difficulty selection flow
    print("\n[Test 5] Testing difficulty selection flow...")
    engine = GameEngine()  # Fresh engine
    events = engine.start()
    print(f"  Initial phase: {engine.s.phase}")

    # Simulate "New Game" action
    events = engine.handle_action("main:new")
    print(f"  After 'main:new': phase={engine.s.phase}")
    print(f"  Number of events returned: {len(events)}")
    for i, event in enumerate(events):
        print(
            f"    Event {i}: type={event.get('type')}, data_keys={list(event.get('data', {}).keys())}"
        )
    assert (
        engine.s.phase == "select_difficulty"
    ), f"Should be in 'select_difficulty' phase, got '{engine.s.phase}'"

    # Check that difficulty menu is displayed
    menu_found = False
    for event in events:
        if event.get("type") == "menu":
            # Menu format uses 'items' with 'id' and 'label' keys
            items = event.get("items", [])
            actions = [item.get("id") for item in items]
            if (
                "difficulty:easy" in actions
                and "difficulty:normal" in actions
                and "difficulty:hard" in actions
            ):
                menu_found = True
                break
    assert menu_found, "Difficulty menu not found in events!"
    print("✓ Difficulty selection menu displayed correctly")

    # Test 6: Test difficulty selection
    print("\n[Test 6] Testing difficulty selection actions...")

    # Select easy
    events = engine.handle_action("difficulty:easy")
    assert (
        engine.s.difficulty == "easy"
    ), f"Difficulty should be 'easy', got '{engine.s.difficulty}'"
    print("✓ Easy difficulty selected successfully")

    # Test 7: Verify stat rolling uses correct dice
    print("\n[Test 7] Verifying stat rolls use difficulty dice...")
    from game.dice import roll_damage

    # Test Easy (6d5): Range 6-30
    engine.s.difficulty = "easy"
    rolls = [roll_damage(engine._get_stat_roll_dice()) for _ in range(100)]
    assert all(
        6 <= r <= 30 for r in rolls
    ), f"Easy rolls outside 6-30 range: {[r for r in rolls if not (6 <= r <= 30)]}"
    print(
        f"✓ Easy (6d5) rolls: min={min(rolls)}, max={max(rolls)}, avg={sum(rolls)/len(rolls):.1f} (expected 18.0)"
    )

    # Test Normal (5d5): Range 5-25
    engine.s.difficulty = "normal"
    rolls = [roll_damage(engine._get_stat_roll_dice()) for _ in range(100)]
    assert all(
        5 <= r <= 25 for r in rolls
    ), f"Normal rolls outside 5-25 range: {[r for r in rolls if not (5 <= r <= 25)]}"
    print(
        f"✓ Normal (5d5) rolls: min={min(rolls)}, max={max(rolls)}, avg={sum(rolls)/len(rolls):.1f} (expected 15.0)"
    )

    # Test Hard (4d5): Range 4-20
    engine.s.difficulty = "hard"
    rolls = [roll_damage(engine._get_stat_roll_dice()) for _ in range(100)]
    assert all(
        4 <= r <= 20 for r in rolls
    ), f"Hard rolls outside 4-20 range: {[r for r in rolls if not (4 <= r <= 20)]}"
    print(
        f"✓ Hard (4d5) rolls: min={min(rolls)}, max={max(rolls)}, avg={sum(rolls)/len(rolls):.1f} (expected 12.0)"
    )

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nDifficulty Selection System Summary:")
    print("  • Three difficulty levels: Easy (6d5), Normal (5d5), Hard (4d5)")
    print("  • Modular configuration in DIFFICULTY_CONFIG")
    print("  • Helper method _get_stat_roll_dice() for centralized logic")
    print("  • New 'select_difficulty' phase after main menu")
    print("  • Stat ranges: Easy (6-30), Normal (5-25), Hard (4-20)")
    print("  • Difficulty stored in state and used only for stat rolling")
    print("\n✨ System is fully functional and ready for use!")


if __name__ == "__main__":
    try:
        test_difficulty_system()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
