from __future__ import annotations

from dataclasses import dataclass, field, asdict
import math
from typing import List, Optional, Dict


@dataclass
class Weapon:
    name: str
    damage_die: str
    damaged: bool = False


@dataclass
class Armor:
    name: str
    armor_class: int
    damaged: bool = False


@dataclass
class Monster:
    name: str
    hp: int
    armor_class: int
    damage_die: str
    gold_reward: int = 0
    dexterity: int = 10
    strength: int = 10


@dataclass
class Companion:
    name: str
    species: str
    hp: int
    max_hp: int
    armor_class: int
    damage_die: str
    strength: int = 0


@dataclass
class MagicItem:
    name: str
    type: str
    effect: str
    cursed: bool = False
    description: str = ""
    bonus: int = 0
    penalty: int = 0
    damage_die: str = ""
    bonus_damage: str = ""


@dataclass
class Character:
    name: str
    clazz: str
    max_hp: int
    gold: int
    hp: int = 1
    weapons: List[Weapon] = field(default_factory=list)  # inventory of weapons
    armor: Optional[Armor] = None  # equipped armor
    attributes: Dict[str, int] = field(default_factory=dict)
    potions: int = 0
    potion_uses: Dict[str, int] = field(default_factory=dict)
    spells: Dict[str, int] = field(default_factory=dict)
    trained_times: int = 0
    persistent_buffs: Dict[str, int] = field(default_factory=dict)
    companion: Optional[Companion] = None
    xp: int = 0
    magic_items: List[MagicItem] = field(default_factory=list)
    # New inventory/equipment fields
    equipped_weapon_index: int = -1  # -1 means unarmed
    armors_owned: List[Armor] = field(default_factory=list)
    level: int = 1
    unspent_stat_points: int = 0
    # Track whether the player has prayed (one-time) while in town. Reset when entering/exiting labyrinth.
    prayed: bool = False
    # Track side quests as a list of dicts: {desc, reward, completed}
    side_quests: List[dict] = field(default_factory=list)
    # Track whether the player has attempted the roll-based rest while in town. Reset when entering/exiting the labyrinth.
    rest_attempted: bool = False
    # New minimal fields to align with updated mechanics/state tracking
    death_count: int = 0
    examine_used_this_turn: bool = False
    attribute_training: Dict[str, int] = field(default_factory=dict)

    def gain_xp(self, amount: int) -> list:
        """Add XP and handle level ups. Returns list of notification strings."""
        messages = []
        self.xp += int(amount)

        # New progression: each level requires (level × 50) XP incrementally.
        # Total XP to reach level L is 50 * (L-1) * L / 2
        def total_xp_for_level(level: int) -> int:
            return (50 * (level - 1) * level) // 2

        while self.xp >= total_xp_for_level(self.level + 1):
            self.level += 1
            self.unspent_stat_points += 1
            messages.append(
                f"You reach level {self.level}! You have {self.unspent_stat_points} unspent stat point(s)."
            )
        return messages

    def gain_level(self) -> list:
        """Spend one unspent stat point to permanently increase an attribute.

        This is interactive: it prompts the player to choose an attribute (similar to
        the `train` flow) and applies +1 to that attribute. Returns messages to be
        printed by the caller.
        """
        messages: list[str] = []
        if self.unspent_stat_points <= 0:
            messages.append(getattr(__import__("builtins"), "repr")(None))
            # Provide a friendly default message
            messages = ["You have no unspent stat points."]
            return messages

        # Attribute selection order (same as UI)
        attrs = [
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ]
        # Prompt loop (spend a single point)
        while self.unspent_stat_points > 0:
            print("Allocate a stat point to an attribute:")
            for i, a in enumerate(attrs, 1):
                val = self.attributes.get(a, 10)
                print(f"{i}) {a} ({val})")
            print(f"{len(attrs) + 1}) Back")
            choice = input("> ").strip()
            if not choice.isdigit():
                messages.append("Invalid choice.")
                return messages
            idx = int(choice) - 1
            if idx == len(attrs):
                # Back / cancel
                messages.append("Level up cancelled.")
                return messages
            if 0 <= idx < len(attrs):
                attr = attrs[idx]
                old_val = self.attributes.get(attr, 10)
                new_val = old_val + 1
                self.attributes[attr] = new_val
                # If Constitution increases, also raise max HP by +5
                if attr == "Constitution":
                    try:
                        self.max_hp += 5
                    except Exception:
                        self.max_hp = int(self.max_hp) + 5
                self.unspent_stat_points -= 1
                messages.append(f"You increase {attr} to {new_val}.")
                # Only spend one point per invocation
                return messages
            # Fallback
            messages.append("Invalid selection.")
            return messages

    def summary(self) -> str:
        # Base AC derived from Constitution and base 10 using new mechanics
        con = int(self.attributes.get("Constitution", 10)) if self.attributes else 10
        base_ac = 10 + math.ceil(con / 2)
        armor_ac = 0
        armor_name = "None"
        if self.armor:
            armor_ac = (
                self.armor.armor_class // 2
                if getattr(self.armor, "damaged", False)
                else self.armor.armor_class
            )
            armor_name = self.armor.name + (
                " (damaged)" if getattr(self.armor, "damaged", False) else ""
            )
        ac = base_ac + armor_ac
        current_weapon = (
            self.weapons[self.equipped_weapon_index].name
            + (
                " (damaged)"
                if 0 <= self.equipped_weapon_index < len(self.weapons)
                and getattr(self.weapons[self.equipped_weapon_index], "damaged", False)
                else ""
            )
            if 0 <= self.equipped_weapon_index < len(self.weapons)
            else "Unarmed"
        )

        # Attributes in fixed order requested by UI
        attr_order = [
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ]
        attr_parts = []
        for key in attr_order:
            val = self.attributes.get(key, 10)
            abbr = key[:3].upper()
            attr_parts.append(f"{abbr} {val}")
        attr_line = ", ".join(attr_parts)

        line1 = f"{self.name} the {self.clazz} (Level {self.level}) | HP {self.hp}/{self.max_hp} | AC {ac} | Gold {self.gold} | XP {self.xp} | Weapon: {current_weapon} | Armor: {armor_name}"
        # Append companion summary if present
        if self.companion:
            comp = self.companion
            comp_line = f"\nCompanion: {comp.name} the {comp.species} | HP {comp.hp}/{comp.max_hp} | AC {comp.armor_class} | STR {getattr(comp, 'strength', 0)} | Damage {comp.damage_die}"
            return line1 + comp_line + "\n " + attr_line
        return line1 + "\n " + attr_line

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "clazz": self.clazz,
            "max_hp": self.max_hp,
            "gold": self.gold,
            "hp": self.hp,
            "weapons": [asdict(w) for w in self.weapons],
            "armor": asdict(self.armor) if self.armor else None,
            "attributes": dict(self.attributes),
            "potions": self.potions,
            "potion_uses": self.potion_uses,
            "spells": self.spells,
            "trained_times": self.trained_times,
            "persistent_buffs": self.persistent_buffs,
            "companion": asdict(self.companion) if self.companion else None,
            "xp": self.xp,
            "magic_items": [asdict(item) for item in self.magic_items],
            "equipped_weapon_index": self.equipped_weapon_index,
            "armors_owned": [asdict(a) for a in self.armors_owned],
            "level": self.level,
            "rest_attempted": bool(self.rest_attempted),
            "prayed": bool(self.prayed),
            "side_quests": [
                (
                    q
                    if isinstance(q, dict)
                    else (q.to_dict() if hasattr(q, "to_dict") else q)
                )
                for q in getattr(self, "side_quests", [])
            ],
            "death_count": int(getattr(self, "death_count", 0)),
            "examine_used_this_turn": bool(
                getattr(self, "examine_used_this_turn", False)
            ),
            "attribute_training": dict(getattr(self, "attribute_training", {})),
        }

    @staticmethod
    def from_dict(data: dict) -> "Character":
        weapons = [Weapon(**w) for w in data.get("weapons", [])]
        armor_data = data.get("armor")
        armor = Armor(**armor_data) if armor_data else None
        char = Character(
            name=data["name"],
            clazz=data["clazz"],
            max_hp=int(data["max_hp"]),
            gold=int(data["gold"]),
        )
        char.hp = int(data.get("hp", char.max_hp))
        char.weapons = weapons
        char.armor = armor
        char.attributes = dict(data.get("attributes", {}))
        char.potions = int(data.get("potions", 0))
        char.potion_uses = dict(data.get("potion_uses", {}))
        char.spells = dict(data.get("spells", {}))
        char.trained_times = int(data.get("trained_times", 0))
        char.persistent_buffs = dict(data.get("persistent_buffs", {}))
        char.xp = int(data.get("xp", 0))
        char.level = int(data.get("level", 1))
        char.magic_items = [MagicItem(**item) for item in data.get("magic_items", [])]
        char.equipped_weapon_index = int(data.get("equipped_weapon_index", -1))
        char.armors_owned = [Armor(**a) for a in data.get("armors_owned", [])]
        comp = data.get("companion")
        if comp:
            char.companion = Companion(**comp)
        # Load rest_attempted flag if present (backwards-compatible)
        char.rest_attempted = bool(data.get("rest_attempted", False))
        char.prayed = bool(data.get("prayed", False))
        # Load side quests if present
        sq = data.get("side_quests", [])
        if sq:
            # store as list of dicts for compatibility
            char.side_quests = [q if isinstance(q, dict) else dict(q) for q in sq]
        # New fields (backwards-compatible defaults)
        char.death_count = int(data.get("death_count", 0))
        char.examine_used_this_turn = bool(data.get("examine_used_this_turn", False))
        char.attribute_training = dict(data.get("attribute_training", {}))
        return char
