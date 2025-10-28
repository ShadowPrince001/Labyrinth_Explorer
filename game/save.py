import json
import os
from typing import Optional

from .entities import Character

SAVE_PATH = os.path.join(os.path.dirname(__file__), "savegame.json")


def save_game(character: Character) -> None:
	try:
		with open(SAVE_PATH, 'w', encoding='utf-8') as f:
			json.dump(character.to_dict(), f, indent=2)
		print(f"Game saved to {SAVE_PATH}")
	except Exception as e:
		print("Failed to save:", e)


def load_game() -> Optional[Character]:
	if not os.path.exists(SAVE_PATH):
		return None
	try:
		with open(SAVE_PATH, 'r', encoding='utf-8') as f:
			data = json.load(f)
		character = Character.from_dict(data)
		# Check if character is dead on-disk (stale save)
		if character.hp <= 0:
			print("Your character has died! Save file deleted.")
			try:
				os.remove(SAVE_PATH)
			except Exception:
				pass
			return None
		return character
	except Exception as e:
		print("Failed to load:", e)
		return None


def clear_save() -> None:
	"""Delete the persistent save file if it exists. Safe to call multiple times."""
	try:
		if os.path.exists(SAVE_PATH):
			os.remove(SAVE_PATH)
			print(f"Save file {SAVE_PATH} cleared.")
	except Exception as e:
		# Non-fatal - just log a message
		print("Failed to clear save:", e)
