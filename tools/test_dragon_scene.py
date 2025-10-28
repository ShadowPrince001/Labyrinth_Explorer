"""
Quick test to show the dragon.png image as a background.
This will emit a scene event to display your dragon image with dramatic text.
"""

import sys
import os
import time
import json

# Add the game directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask
from flask_socketio import SocketIO
from game.scene_manager import create_scene_event


def test_dragon_scene():
    """Test the dragon background image"""

    print("🐉 Testing Dragon Background Image")
    print("=" * 40)

    # Create the dragon scene event
    dragon_scene = create_scene_event(
        "dragon.png",
        "A mighty dragon emerges from the shadows, its eyes glowing with ancient fire! The ground trembles beneath its massive claws as it spreads its wings wide, blocking out the sun.",
    )

    print("Scene Event Created:")
    print(json.dumps(dragon_scene, indent=2))
    print()

    # Show what this would look like in your game
    print("🎮 In Your Game Code:")
    print("```python")
    print("from game.scene_manager import create_scene_event")
    print("")
    print("# Add dragon encounter scene")
    print('events.append(create_scene_event("dragon.png", "A mighty dragon appears!"))')
    print("_emit_events(events)  # Send to frontend")
    print("```")
    print()

    print("🌟 Visual Result:")
    print("- Background: Full-screen dragon.png image")
    print("- Text: Dramatic dragon encounter text in translucent overlay")
    print("- Position: Text appears in bottom half of screen")
    print("- Style: Professional, atmospheric game presentation")

    return dragon_scene


if __name__ == "__main__":
    test_dragon_scene()
