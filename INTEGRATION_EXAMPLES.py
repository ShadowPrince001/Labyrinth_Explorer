"""
Example integration showing how to add scene events to your existing game code.

This demonstrates how to integrate the new background image system into your
DnD game's existing event structure.
"""

# Example: Adding scene events to your town.py or dungeon.py


def enter_tavern_example(events):
    """
    Example of how to add a scene event when player enters the tavern.
    """
    from .scene_manager import tavern_scene

    # Add the scene event BEFORE the dialogue
    events.append(tavern_scene("The tavern door creaks open as you step inside..."))

    # Your existing dialogue/menu logic continues normally
    events.append(
        {
            "type": "dialogue",
            "data": {"text": "The bartender looks up and nods at you."},
        }
    )
    # ... rest of your tavern logic


def enter_dungeon_example(events):
    """
    Example of adding scene when entering dungeon.
    """
    from .scene_manager import dungeon_entrance_scene

    # Set the dramatic scene
    events.append(dungeon_entrance_scene())

    # Then continue with your existing logic
    events.append(
        {
            "type": "dialogue",
            "data": {"text": "You feel a chill as you approach the entrance..."},
        }
    )


def battle_scene_example(events, monster_name):
    """
    Example of changing background during combat.
    """
    from .scene_manager import create_scene_event

    # Change to battle background
    events.append(create_scene_event("battle.jpg", f"A {monster_name} appears!"))

    # Your existing combat logic continues
    events.append({"type": "combat", "data": {"text": "Roll for initiative!"}})


def treasure_found_example(events):
    """
    Example of scene change when finding treasure.
    """
    from .scene_manager import treasure_room_scene

    # Dramatic treasure room reveal
    events.append(treasure_room_scene("Your torch illuminates piles of gold and gems!"))

    # Continue with treasure logic
    events.append(
        {"type": "dialogue", "data": {"text": "You have discovered a treasure hoard!"}}
    )


# INTEGRATION PATTERNS:

# Pattern 1: Scene + Text in one event
# events.append(tavern_scene("Custom text here..."))

# Pattern 2: Scene + Separate dialogue
# events.append(create_scene_event("background.jpg"))  # Just background
# events.append({"type": "dialogue", "data": {"text": "Separate text event"}})

# Pattern 3: Scene transitions during gameplay
# events.append(create_scene_event("old_scene.jpg"))
# # ... some game logic ...
# events.append(create_scene_event("new_scene.jpg", "Scene changes..."))

# Pattern 4: Clear background for text-only sections
# events.append(create_scene_event(None, "You enter a void..."))
