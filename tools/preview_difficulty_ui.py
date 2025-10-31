"""Preview the difficulty selection UI."""

import sys, os

root = os.path.dirname(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

from game.engine import GameEngine


def preview_ui():
    print("\n" + "=" * 70)
    print("DIFFICULTY SELECTION UI PREVIEW")
    print("=" * 70 + "\n")

    engine = GameEngine()
    engine.start()

    # Trigger difficulty selection
    events = engine.handle_action("main:new")

    print("\n" + "=" * 70)
    print("EVENTS GENERATED:")
    print("=" * 70 + "\n")

    for i, event in enumerate(events):
        event_type = event.get("type", "unknown")

        if event_type == "dialogue":
            # Extract text from data
            text = event.get("data", {}).get("text", "") or event.get("text", "")
            if text:
                print(text)
        elif event_type == "menu":
            items = event.get("items", [])
            print(f"\n[Menu Options:]")
            for item in items:
                label = item.get("label", "")
                print(f"  • {label}")
        elif event_type == "clear":
            print("[Screen Cleared]")
        elif event_type == "state":
            print(
                f"\n[State Updated: phase={engine.s.phase}, difficulty={engine.s.difficulty}]"
            )

    print("\n" + "=" * 70)
    print("DIFFICULTY CONFIGURATION:")
    print("=" * 70 + "\n")

    for key in ["easy", "normal", "hard"]:
        config = engine.DIFFICULTY_CONFIG[key]
        print(f"{config['name'].upper()} ({config['dice']}):")
        print(f"  Dice: {config['dice']}")
        print(f"  Description: {config['description']}")

        # Calculate ranges
        dice_parts = config["dice"].split("d")
        num_dice = int(dice_parts[0])
        die_size = int(dice_parts[1])
        min_stat = num_dice
        max_stat = num_dice * die_size
        print(f"  Range: {min_stat}-{max_stat}")
        print()


if __name__ == "__main__":
    preview_ui()
