from __future__ import annotations

import random
from typing import Optional

from .dice import roll_damage
from .entities import Character, MagicItem, Weapon
from .data_loader import load_magic_items, get_dialogue


def random_magic_item() -> Optional[MagicItem]:
	items = load_magic_items()
	if not items:
		return None
	return MagicItem(**random.choice(items))


def examine_item(item: MagicItem) -> str:
	status = "CURSED" if item.cursed else "Blessed"
	desc = f"{item.name} ({item.type}) - {status}\n{item.description}"
	
	if item.bonus > 0:
		desc += f"\nBonus: +{item.bonus}"
	if item.penalty > 0:
		desc += f"\nPenalty: -{item.penalty}"
	if item.damage_die:
		desc += f"\nDamage: {item.damage_die}"
	if item.bonus_damage:
		desc += f"\nBonus Damage: {item.bonus_damage}"
	
	return desc


def equip_magic_item(character: Character, item: MagicItem) -> bool:
	if item.type == "weapon":
		# Add as weapon
		weapon = Weapon(name=item.name, damage_die=item.damage_die)
		character.weapons.append(weapon)
		msg = get_dialogue('items', 'equip_blessed', None, character)
		print(msg or f"You equip the {item.name}.")
		return True
	else:
		# Add to magic items inventory
		character.magic_items.append(item)
		msg = get_dialogue('items', 'equip_passive', None, character)
		print(msg or f"You take the {item.name}.")
		
		# Apply immediate effects if cursed
		if item.cursed:
			apply_cursed_effect(character, item)
		else:
			apply_blessed_effect(character, item)
		return True


def apply_blessed_effect(character: Character, item: MagicItem) -> None:
	effect = item.effect
	bonus = item.bonus

	if effect == "strength_bonus":
		character.attributes["Strength"] = character.attributes.get("Strength", 10) + bonus
		msg = get_dialogue('items', 'stat_increase', None, character)
		print(msg.format(stat='Strength', bonus=bonus) if msg else f"Your strength increases by {bonus}!")
	elif effect == "dexterity_bonus":
		character.attributes["Dexterity"] = character.attributes.get("Dexterity", 10) + bonus
		msg = get_dialogue('items', 'stat_increase', None, character)
		print(msg.format(stat='Dexterity', bonus=bonus) if msg else f"Your dexterity increases by {bonus}!")
	elif effect == "intelligence_bonus":
		character.attributes["Intelligence"] = character.attributes.get("Intelligence", 10) + bonus
		msg = get_dialogue('items', 'stat_increase', None, character)
		print(msg.format(stat='Intelligence', bonus=bonus) if msg else f"Your intelligence increases by {bonus}!")
	elif effect == "wisdom_bonus":
		character.attributes["Wisdom"] = character.attributes.get("Wisdom", 10) + bonus
		msg = get_dialogue('items', 'stat_increase', None, character)
		print(msg.format(stat='Wisdom', bonus=bonus) if msg else f"Your wisdom increases by {bonus}!")
	elif effect == "charisma_bonus":
		character.attributes["Charisma"] = character.attributes.get("Charisma", 10) + bonus
		msg = get_dialogue('items', 'stat_increase', None, character)
		print(msg.format(stat='Charisma', bonus=bonus) if msg else f"Your charisma increases by {bonus}!")
	elif effect == "perception_bonus":
		character.attributes["Perception"] = character.attributes.get("Perception", 10) + bonus
		msg = get_dialogue('items', 'stat_increase', None, character)
		print(msg.format(stat='Perception', bonus=bonus) if msg else f"Your perception increases by {bonus}!")


def apply_cursed_effect(character: Character, item: MagicItem) -> None:
	effect = item.effect
	penalty = item.penalty
	
	if effect == "strength_penalty":
		character.attributes["Strength"] = max(1, character.attributes.get("Strength", 10) - penalty)
		msg = get_dialogue('items', 'stat_decrease', None, character)
		print(msg.format(stat='Strength', penalty=penalty) if msg else f"Your strength decreases by {penalty}!")
	elif effect == "dexterity_penalty":
		character.attributes["Dexterity"] = max(1, character.attributes.get("Dexterity", 10) - penalty)
		msg = get_dialogue('items', 'stat_decrease', None, character)
		print(msg.format(stat='Dexterity', penalty=penalty) if msg else f"Your dexterity decreases by {penalty}!")
	elif effect == "intelligence_penalty":
		character.attributes["Intelligence"] = max(1, character.attributes.get("Intelligence", 10) - penalty)
		msg = get_dialogue('items', 'stat_decrease', None, character)
		print(msg.format(stat='Intelligence', penalty=penalty) if msg else f"Your intelligence decreases by {penalty}!")
	elif effect == "wisdom_penalty":
		character.attributes["Wisdom"] = max(1, character.attributes.get("Wisdom", 10) - penalty)
		msg = get_dialogue('items', 'stat_decrease', None, character)
		print(msg.format(stat='Wisdom', penalty=penalty) if msg else f"Your wisdom decreases by {penalty}!")
	elif effect == "charisma_penalty":
		character.attributes["Charisma"] = max(1, character.attributes.get("Charisma", 10) - penalty)
		msg = get_dialogue('items', 'stat_decrease', None, character)
		print(msg.format(stat='Charisma', penalty=penalty) if msg else f"Your charisma decreases by {penalty}!")
	elif effect == "perception_penalty":
		character.attributes["Perception"] = max(1, character.attributes.get("Perception", 10) - penalty)
		msg = get_dialogue('items', 'stat_decrease', None, character)
		print(msg.format(stat='Perception', penalty=penalty) if msg else f"Your perception decreases by {penalty}!")
	elif effect == "noise":
		character.persistent_buffs["debuff_noise"] = 1
		msg = get_dialogue('items', 'noise_cursed', None, character)
		print(msg or "The item makes noise when you move!")
	elif effect == "weapon_damage":
		# Damage currently equipped weapon
		if character.weapons:
			weapon = character.weapons[0]
			# Mark weapon as damaged (reduced effectiveness)
			if hasattr(weapon, 'damaged'):
				weapon.damaged = True
			else:
				# fallback: attach attribute for older saves
				setattr(weapon, 'damaged', True)
			msg = get_dialogue('items', 'weapon_damaged', None, character)
			print(msg.format(name=weapon.name) if msg else f"Your {weapon.name} is damaged and its effectiveness is reduced!")


def use_wand(character: Character, item: MagicItem) -> bool:
	if item.type != "wand":
		msg = get_dialogue('items', 'not_a_wand', None, character)
		print(msg or "That's not a wand!")
		return False
	
	effect = item.effect
	if effect == "fireball":
		msg = get_dialogue('items', 'wand_fireball', None, character)
		print(msg or "You wave the wand and a fireball shoots out!")
		return True  # Could be used in combat
	elif effect == "lightning":
		msg = get_dialogue('items', 'wand_lightning', None, character)
		print(msg or "You wave the wand and lightning crackles!")
		return True
	elif effect == "water_blast":
		msg = get_dialogue('items', 'wand_water', None, character)
		print(msg or "You wave the wand and water blasts out!")
		return True
	else:
		msg = get_dialogue('items', 'wand_fail', None, character)
		print(msg or "The wand doesn't seem to work.")
		return False


def remove_cursed_item(character: Character, item_name: str) -> bool:
	# Find and remove cursed item
	for i, item in enumerate(character.magic_items):
		if item.name.lower() == item_name.lower() and item.cursed:
			# Reverse the curse effects
			reverse_cursed_effect(character, item)
			character.magic_items.pop(i)
			msg = get_dialogue('items', 'remove_cursed', None, character)
			print(msg.format(name=item.name) if msg else f"You remove the cursed {item.name}.")
			return True
		msg = get_dialogue('items', 'no_cursed_found', None, character)
		print(msg or "No such cursed item found.")
	return False


def reverse_cursed_effect(character: Character, item: MagicItem) -> None:
	effect = item.effect
	penalty = item.penalty
	
	if effect == "strength_penalty":
		character.attributes["Strength"] = character.attributes.get("Strength", 10) + penalty
	elif effect == "dexterity_penalty":
		character.attributes["Dexterity"] = character.attributes.get("Dexterity", 10) + penalty
	elif effect == "intelligence_penalty":
		character.attributes["Intelligence"] = character.attributes.get("Intelligence", 10) + penalty
	elif effect == "wisdom_penalty":
		character.attributes["Wisdom"] = character.attributes.get("Wisdom", 10) + penalty
	elif effect == "charisma_penalty":
		character.attributes["Charisma"] = character.attributes.get("Charisma", 10) + penalty
	elif effect == "perception_penalty":
		character.attributes["Perception"] = character.attributes.get("Perception", 10) + penalty
	elif effect == "noise":
		character.persistent_buffs.pop("debuff_noise", None)


def auto_equip_magic_item(character: Character, item_name: str) -> bool:
	"""Auto-equip a magic item by name (cannot be removed)."""
	magic_items = load_magic_items()
	item_data = next((item for item in magic_items if item.get('name') == item_name), None)
	
	if not item_data:
		msg = get_dialogue('items', 'unknown_item', None, None)
		print(msg.format(name=item_name) if msg else f"Unknown item: {item_name}")
		return False
	
	# Create magic item object
	item = MagicItem(
		name=item_data.get('name', 'Unknown'),
		type=item_data.get('type', 'unknown'),
		effect=item_data.get('effect', ''),
		bonus=item_data.get('bonus', 0),
		penalty=item_data.get('penalty', 0),
		damage_die=item_data.get('damage_die', ''),
		bonus_damage=item_data.get('bonus_damage', ''),
		cursed=item_data.get('cursed', False),
		description=item_data.get('description', '')
	)
	
	# Auto-equip based on type
	if item.type == "weapon":
		# Add as weapon
		weapon = Weapon(name=item.name, damage_die=item.damage_die)
		character.weapons.append(weapon)
		msg = get_dialogue('items', 'auto_equip', None, character)
		print(msg.format(name=item.name) if msg else f"The {item.name} is automatically equipped!")
		return True
	elif item.type == "ring":
		# Apply ring effects directly to character
		apply_ring_effects(character, item)
		msg = get_dialogue('items', 'auto_equip_locked', None, character)
		print(msg.format(name=item.name) if msg else f"The {item.name} is automatically equipped and cannot be removed!")
		return True
	else:
		# Add to magic items inventory
		character.magic_items.append(item)
		msg = get_dialogue('items', 'auto_equip', None, character)
		print(msg.format(name=item.name) if msg else f"The {item.name} is automatically equipped!")
		return True


def apply_ring_effects(character: Character, ring: MagicItem) -> None:
	"""Apply ring effects directly to character attributes."""
	effect = ring.effect
	
	# Get weighted bonus/penalty value
	if ring.bonus > 0:
		value = get_weighted_bonus(ring.bonus)
		attribute = effect.replace("_bonus", "")
		character.attributes[attribute] = character.attributes.get(attribute, 10) + value
	elif ring.penalty > 0:
		value = get_weighted_penalty(ring.penalty)
		attribute = effect.replace("_penalty", "")
		character.attributes[attribute] = character.attributes.get(attribute, 10) - value


def get_weighted_bonus(bonus_str: str) -> int:
	"""Get weighted bonus value from string like '2–5 (weighted 50%,30%,20%)'."""
	import random
	
	# Parse the bonus string to get weighted values
	if "2–5" in bonus_str:
		# 50% chance for 2, 30% chance for 3, 20% chance for 4-5
		roll = random.random()
		if roll < 0.5:
			return 2
		elif roll < 0.8:
			return 3
		else:
			return random.randint(4, 5)
	else:
		# Default to 2 if parsing fails
		return 2


def get_weighted_penalty(penalty_str: str) -> int:
	"""Get weighted penalty value from string like '1–3 (weighted 50%,30%,20%)'."""
	import random
	
	# Parse the penalty string to get weighted values
	if "1–3" in penalty_str:
		# 50% chance for 1, 30% chance for 2, 20% chance for 3
		roll = random.random()
		if roll < 0.5:
			return 1
		elif roll < 0.8:
			return 2
		else:
			return 3
	else:
		# Default to 1 if parsing fails
		return 1
