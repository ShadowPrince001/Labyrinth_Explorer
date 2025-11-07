"""
Scene Manager for handling background images and visual events in the DnD game.

This module provides helper functions for emitting scene events with background
images and overlay text to create immersive visual experiences.
"""

import re


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
    """Set background based on room description with precise matching.

    Strategy:
    - Prefer explicit shape near a room noun (room|hall|chamber|gallery|vault).
    - Use word boundaries to avoid false positives (e.g., "square-cut").
    - Fall back to generic nouns if no shape is found.
    """
    room_desc = (room_description or "").lower()

    # Common room nouns and shapes
    nouns = r"(?:room|hall|chamber|gallery|vault)"

    patterns = [
        # Rectangular explicitly near a noun
        (
            rf"\brectangular\b[^\n\r]*\b{nouns}\b|\b{nouns}\b[^\n\r]*\brectangular\b",
            "rooms/rectangular_hall.png",
        ),
        (
            rf"\brectangle\b[^\n\r]*\b{nouns}\b|\b{nouns}\b[^\n\r]*\brectangle\b",
            "rooms/rectangular_hall.png",
        ),
        # Square explicitly near a noun or clear phrases like "perfectly square"
        (
            rf"\bsquare\b[^\n\r]*\b{nouns}\b|\b{nouns}\b[^\n\r]*\bsquare\b",
            "rooms/square_vault.png",
        ),
        (r"\bperfectly\s+square\b", "rooms/square_vault.png"),
        # Hexagonal / Triangular / Oval / Circular
        (r"\bhexagonal\b", "rooms/hexagonal_pillared_room.png"),
        # Note: image file is intentionally misspelled as "traingular_chamber.png"
        (r"\btriangular\b", "rooms/traingular_chamber.png"),
        (r"\boval\b", "rooms/oval_gallery.png"),
        (r"\bcircular\b|\bcircle\b", "rooms/circular_chamber.png"),
    ]

    for pat, img in patterns:
        try:
            if re.search(pat, room_desc):
                return create_scene_event(img)
        except re.error:
            # If a pattern fails to compile for some reason, skip it safely
            continue

    # Secondary heuristics (no explicit shape found)
    if re.search(r"\bvault\b", room_desc):
        return create_scene_event("rooms/square_vault.png")
    if re.search(r"\bpillared\b", room_desc):
        return create_scene_event("rooms/hexagonal_pillared_room.png")
    if re.search(r"\bgallery\b", room_desc):
        return create_scene_event("rooms/oval_gallery.png")
    if re.search(r"\bhall\b", room_desc):
        return create_scene_event("rooms/rectangular_hall.png")
    if re.search(r"\bchamber\b|\broom\b", room_desc):
        return create_scene_event("rooms/circular_chamber.png")

    # Fallback
    return create_scene_event("labyrinth.png")


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
