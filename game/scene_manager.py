"""
Scene Manager for handling background images and visual events in the DnD game.

This module provides helper functions for emitting scene events with background
images and overlay text to create immersive visual experiences.
"""


def create_scene_event(background=None, text=""):
    """
    Create a scene event with background image and optional text.

    Args:
        background (str): Filename of the background image (e.g., "dragon.png")
        text (str): Optional text to overlay on the scene

    Returns:
        dict: Event dictionary for the game engine
    """
    return {"type": "scene", "data": {"background": background, "text": text}}


def set_town_background():
    """Set background to town_menu/town.png for town activities"""
    return create_scene_event("town_menu/town.png")


def set_labyrinth_background():
    """Set background to labyrinth.png for character creation and general labyrinth"""
    return create_scene_event("labyrinth.png")


def set_death_background():
    """Set background to death.png for defeat/revival screens"""
    return create_scene_event("death.png")


def set_room_background(room_description):
    """Set background based on room description - match to actual image filenames"""
    room_desc = room_description.lower()

    # Map room descriptions to actual image filenames
    if "circular" in room_desc or "chamber" in room_desc:
        return create_scene_event("rooms/circular_chamber.png")
    elif "rectangular" in room_desc or "hall" in room_desc:
        return create_scene_event("rooms/rectangular_hall.png")
    elif "hexagonal" in room_desc or "pillared" in room_desc:
        return create_scene_event("rooms/hexagonal_pillared_room.png")
    elif "triangular" in room_desc:
        return create_scene_event(
            "rooms/traingular_chamber.png"
        )  # Note: image has typo "traingular"
    elif "oval" in room_desc or "gallery" in room_desc:
        return create_scene_event("rooms/oval_gallery.png")
    elif "square" in room_desc or "vault" in room_desc:
        return create_scene_event("rooms/square_vault.png")
    else:
        return create_scene_event("labyrinth.png")  # fallback


def dragon_entrance_scene():
    """Create the dramatic dragon entrance scene"""
    return create_scene_event(
        "dragon.png",
        "🐉 A MIGHTY DRAGON EMERGES! 🐉\n\nThe ancient beast rises from the depths, its scales glinting like obsidian in the flickering torchlight. Steam rises from its nostrils as it fixes you with eyes that burn like molten gold.\n\n'Who dares disturb my slumber?' the dragon rumbles, its voice shaking the very foundations of the dungeon.",
    )


def vault_scene(
    text="💰 THE TREASURE VAULT 💰\n\nYou step into a magnificent square chamber with low vaulted ceilings. Ancient stone walls glisten with moisture, and the air is thick with the scent of old gold. Piles of treasure gleam in the dim light, but something feels... wrong. The silence is too complete, too expectant.",
):
    """Helper for square vault scene."""
    return create_scene_event("rooms/square_vault.png", text)


def set_monster_background(name: str):
    """Set battle background to a monster image if available.

    Maps monster names like "Death Knight" -> "monsters/death_knight.png".
    """
    slug = (name or "").lower().replace(" ", "_")
    return create_scene_event(f"monsters/{slug}.png")


def clear_background():
    """Clear the background image."""
    return create_scene_event(None, "")


# Example usage in your game code:
# events.append(dungeon_entrance_scene())
# events.append(create_scene_event("custom_image.jpg", "Custom text here"))
