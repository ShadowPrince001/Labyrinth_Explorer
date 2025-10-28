"""
Test script to demonstrate the new scene/background image functionality.

Run this script to see how to emit scene events with background images.
"""

import sys
import os

# Add the game directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from game.scene_manager import (
    create_scene_event,
    dungeon_entrance_scene,
    forest_scene,
    tavern_scene,
)


def test_scene_events():
    """
    Example of how to use scene events in your game logic.
    """

    # Example event queue that your game engine would process
    events = []

    # Scenario: Player enters a new area
    print("=== Scene Event Examples ===\n")

    # 1. Dungeon entrance with helper function
    dungeon_event = dungeon_entrance_scene(
        "The ancient stones are covered in mysterious runes..."
    )
    events.append(dungeon_event)
    print("1. Dungeon Entrance Event:")
    print(f"   Background: {dungeon_event['data']['background']}")
    print(f"   Text: {dungeon_event['data']['text']}\n")

    # 2. Custom forest scene
    forest_event = create_scene_event(
        "forest_clearing.jpg", "Birds chirp peacefully in the distance."
    )
    events.append(forest_event)
    print("2. Forest Scene Event:")
    print(f"   Background: {forest_event['data']['background']}")
    print(f"   Text: {forest_event['data']['text']}\n")

    # 3. Tavern scene with helper
    tavern_event = tavern_scene()  # Uses default text
    events.append(tavern_event)
    print("3. Tavern Scene Event:")
    print(f"   Background: {tavern_event['data']['background']}")
    print(f"   Text: {tavern_event['data']['text']}\n")

    # 4. Background change without text
    background_only = create_scene_event("dark_cave.jpg")
    events.append(background_only)
    print("4. Background Only Event:")
    print(f"   Background: {background_only['data']['background']}")
    print(f"   Text: '{background_only['data']['text']}'\n")

    # 5. Clear background
    clear_bg = create_scene_event(None, "You step into darkness...")
    events.append(clear_bg)
    print("5. Clear Background Event:")
    print(f"   Background: {clear_bg['data']['background']}")
    print(f"   Text: {clear_bg['data']['text']}\n")

    print("=== Integration Example ===")
    print("In your game engine, you would emit these events like:")
    print("```python")
    print("from game.scene_manager import dungeon_entrance_scene")
    print("")
    print("# In your game logic:")
    print("events = []")
    print("events.append(dungeon_entrance_scene())")
    print("_emit_events(events)  # This sends to the frontend")
    print("```")

    return events


if __name__ == "__main__":
    test_scene_events()
