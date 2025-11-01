#!/usr/bin/env python3
"""
FIXED RPG Character Simulation - 100 Full Runs
Corrected based on actual game mechanics verification.

Key Fixes Applied:
1. Examine doesn't trigger monster attack (can use once per combat)
2. Divine ALWAYS triggers monster attack (even on success)
3. Dragon stats: HP 135, AC 31, damage 8d7 (32 avg)
4. Win condition: Track Dragon victories (not just deaths)
5. Monster stats: Fixed base values (no depth scaling)
6. Town visits: Only after start + revivals (not every depth)
"""

import sys
import os
import random
import json
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

# Add game directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.entities import Character, Monster, Weapon, Armor
from game.dice import roll_damage
from game.combat import compute_armor_class
from game.data_loader import load_weapons, load_armors, load_monsters


@dataclass
class SimulationMetrics:
    """Comprehensive metrics for a single character run"""

    character_name: str = ""
    starting_stats: Dict[str, int] = field(default_factory=dict)

    # Outcome
    won_game: bool = False  # Beat Dragon = Victory
    permanent_death: bool = False
    total_turns: int = 0
    total_encounters: int = 0
    dragon_encountered: bool = False

    # Progression
    max_depth_reached: int = 0
    max_level_reached: int = 1
    final_gold: int = 0

    # Combat stats
    total_attacks: int = 0
    attacks_hit: int = 0
    attacks_missed: int = 0
    attacks_blocked: int = 0
    critical_hits: int = 0

    damage_dealt: int = 0
    damage_taken: int = 0

    monsters_killed: int = 0
    deaths: int = 0
    revivals: int = 0

    # Charm tracking (engine-level feature not used in this simulator, but kept for parity)
    charms_attempted: int = 0
    charms_success: int = 0

    # Action usage
    divine_used: int = 0
    divine_success: int = 0
    examine_used: int = 0
    potions_used: int = 0
    spells_cast: int = 0

    # Economy
    gold_earned: int = 0
    gold_spent_weapons: int = 0
    gold_spent_armor: int = 0
    gold_spent_potions: int = 0
    gold_spent_training: int = 0

    weapons_bought: int = 0
    armor_bought: int = 0
    potions_bought: int = 0

    # Training
    training_sessions: int = 0
    stats_trained: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Town visits
    town_visits: int = 0

    # Additional per-run telemetry
    unique_monsters: set = field(default_factory=set)
    death_reasons: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    # Quests
    quests_completed: int = 0
    quest_gold_earned: int = 0

    # Final stats
    final_stats: Dict[str, int] = field(default_factory=dict)
    final_hp: int = 0
    final_max_hp: int = 0

    def hit_rate(self) -> float:
        total = self.attacks_hit + self.attacks_missed + self.attacks_blocked
        return (self.attacks_hit / total * 100) if total > 0 else 0

    def divine_success_rate(self) -> float:
        return (
            (self.divine_success / self.divine_used * 100)
            if self.divine_used > 0
            else 0
        )

    def avg_damage_per_encounter(self) -> float:
        return (
            self.damage_dealt / self.total_encounters
            if self.total_encounters > 0
            else 0
        )


class SmartAI:
    """AI that makes intelligent decisions based on game state"""

    @staticmethod
    def allocate_stats_smart(character: Character, rolls: List[int]):
        """Allocate rolled stats intelligently.
        Priority: STR > CON > DEX > WIS > INT > CHA > PER
        (STR for hit rate and damage, CON for HP)
        """
        sorted_rolls = sorted(rolls, reverse=True)
        priority = [
            "Strength",
            "Constitution",
            "Dexterity",
            "Wisdom",
            "Intelligence",
            "Charisma",
            "Perception",
        ]

        for stat, roll in zip(priority, sorted_rolls):
            character.attributes[stat] = roll

    @staticmethod
    def should_visit_town(char: Character, depth: int, just_revived: bool) -> bool:
        """Decide if we should return to town.
        Rules:
        - Always after revival
        - If HP < 60%
        - If potions < 2
        - If we likely can afford an upgrade (gold >= 40 for weapon or >= 60 for armor)
        - Before pushing into depth >= 4 (one-time pre-push gear-up)
        """
        if just_revived:
            return True
        hp_ok = char.max_hp > 0 and (char.hp / char.max_hp) >= 0.6
        pot_ok = char.potions >= 2
        gold_ok = not (char.gold >= 40 or char.gold >= 60)
        if (not hp_ok) or (not pot_ok) or (not gold_ok):
            return True
        return False

    @staticmethod
    def choose_training_attribute(char: Character) -> Optional[str]:
        """Choose which attribute to train.
        Strategy: STR to 18, then CON to 18, then alternate
        """
        str_val = char.attributes.get("Strength", 10)
        con_val = char.attributes.get("Constitution", 10)

        # Priority 1: Get STR to 18 (hit rate + damage)
        if str_val < 18:
            return "Strength"

        # Priority 2: Get CON to 18 (HP for Dragon fight)
        if con_val < 18:
            return "Constitution"

        # Priority 3: Continue STR to 20
        if str_val < 20:
            return "Strength"

        # Priority 4: Continue CON to 20
        if con_val < 20:
            return "Constitution"

        return None

    @staticmethod
    def should_buy_weapon(
        char: Character, available_weapons: List[Weapon]
    ) -> Optional[Dict]:
        """Decide if we should upgrade weapon"""
        if not available_weapons:
            return None

        # Consider only shop-available weapons with a positive (or defined) price
        candidates = [w for w in available_weapons if w.get("availability") == "shop"]

        current_weapon = char.weapons[0] if char.weapons else None

        # Parse damage dice to compare
        def avg_damage(dice_str: str) -> float:
            if not dice_str or "d" not in dice_str:
                return 2.0
            try:
                num, sides = dice_str.split("d")
                return int(num) * (int(sides) + 1) / 2
            except:
                return 2.0

        current_avg = avg_damage(current_weapon.damage_die) if current_weapon else 2.0

        # Find best affordable upgrade
        best_weapon = None
        best_avg = current_avg

        for weapon in candidates:
            cost = weapon.get("price", weapon.get("cost", 999))
            if cost <= char.gold:
                weapon_avg = avg_damage(weapon.get("damage_die", "1d4"))
                if weapon_avg > best_avg:
                    best_weapon = weapon
                    best_avg = weapon_avg

        return best_weapon

    @staticmethod
    def should_buy_armor(
        char: Character, available_armor: List[Dict]
    ) -> Optional[Dict]:
        """Decide if we should upgrade armor"""
        if not available_armor:
            return None

        # Consider only shop-available armor
        candidates = [a for a in available_armor if a.get("availability") == "shop"]

        current_ac = char.armor.armor_class if char.armor else 0

        # Find best affordable upgrade
        best_armor = None
        best_ac = current_ac

        for armor in candidates:
            cost = armor.get("price", armor.get("cost", 999))
            ac = armor.get("armor_class", 0)
            if cost <= char.gold and ac > best_ac:
                best_armor = armor
                best_ac = ac

        return best_armor

    @staticmethod
    def should_use_potion(char: Character, monster_hp: int) -> bool:
        """Decide if we should use a healing potion.
        Use if: HP < 50% AND have potions AND monster still dangerous
        """
        if char.potions <= 0:
            return False

        hp_percent = char.hp / char.max_hp if char.max_hp > 0 else 0

        # Use potion if below 50% HP
        return hp_percent < 0.5

    @staticmethod
    def should_use_divine(char: Character, monster: Monster) -> bool:
        """Decide if we should use Divine Aid.
        Use if: HP < 30% (desperate) AND high WIS (15+)
        NOTE: Divine always triggers monster attack, so risky!
        """
        wis = char.attributes.get("Wisdom", 10)
        hp_percent = char.hp / char.max_hp if char.max_hp > 0 else 0

        # Only use if desperate AND high WIS
        return hp_percent < 0.3 and wis >= 15

    @staticmethod
    def should_examine(
        char: Character, monster: Monster, examined_this_combat: bool
    ) -> bool:
        """Decide if we should examine monster.
        Examine: Once per combat, doesn't trigger attack, useful vs tough monsters
        """
        if examined_this_combat:
            return False

        # Examine tough monsters (AC 20+)
        return monster.armor_class >= 20


class GameSimulator:
    """Simulates full character runs"""

    def __init__(self):
        self.weapons = load_weapons()
        self.armors = load_armors()
        self.monsters_data = load_monsters()

    @staticmethod
    def _stat_dice_for_difficulty(difficulty: str) -> str:
        d = (difficulty or "normal").lower()
        if d == "easy":
            return "6d5"
        if d == "hard":
            return "4d5"
        return "5d5"  # normal

    def create_monster(self, name: str = None, depth: int = 1) -> Monster:
        """Create a monster from data (fixed base stats, no scaling)"""
        if name:
            entry = next((m for m in self.monsters_data if m.get("name") == name), None)
        else:
            # Random monster based on depth (but stats are fixed from data)
            eligible = [
                m for m in self.monsters_data if m.get("difficulty", 0) <= depth + 2
            ]
            if not eligible:
                eligible = self.monsters_data
            entry = random.choice(eligible)

        if not entry:
            # Fallback
            return Monster("Goblin", 10, 12, "1d4")

        return Monster(
            name=entry["name"],
            hp=entry["base_hp"],
            armor_class=entry["base_ac"],
            damage_die=entry["damage_die"],
            strength=entry.get("base_strength", 10),
            dexterity=entry.get("base_dex", 10),
        )

    def town_phase(
        self, char: Character, metrics: SimulationMetrics, first_visit: bool = False
    ):
        """Handle town activities: shop, train, heal"""
        metrics.town_visits += 1

        # Heal to full
        char.hp = char.max_hp

        # Buy starting gear on first visit
        if first_visit:
            # Buy best weapon we can afford (prioritize Longsword 1d8 for 40g)
            weapon_dict = SmartAI.should_buy_weapon(char, self.weapons)
            if weapon_dict:
                cost = weapon_dict.get("price", weapon_dict.get("cost", 0))
                char.gold -= cost
                weapon = Weapon(
                    name=weapon_dict["name"], damage_die=weapon_dict["damage_die"]
                )
                char.weapons = [weapon]
                metrics.gold_spent_weapons += cost
                metrics.weapons_bought += 1

            # Buy best armor we can afford (prioritize Leather Armor AC 12 for 60g)
            armor_dict = SmartAI.should_buy_armor(char, self.armors)
            if armor_dict:
                cost = armor_dict.get("price", armor_dict.get("cost", 0))
                char.gold -= cost
                armor = Armor(
                    name=armor_dict["name"], armor_class=armor_dict["armor_class"]
                )
                char.armor = armor
                metrics.gold_spent_armor += cost
                metrics.armor_bought += 1

            # Buy 2 potions for emergency (20g each)
            potions_to_buy = min(2, char.gold // 20)
            if potions_to_buy > 0:
                char.potions += potions_to_buy
                cost = potions_to_buy * 20
                char.gold -= cost
                metrics.gold_spent_potions += cost
                metrics.potions_bought += potions_to_buy
        # Subsequent visits: upgrade and train
        else:
            # Try to train if we have 50g+ and need stats
            if char.gold >= 50:
                attr = SmartAI.choose_training_attribute(char)
                if attr:
                    char.attributes[attr] = char.attributes.get(attr, 10) + 1
                    char.gold -= 50
                    char.max_hp = 10 + char.attributes.get("Constitution", 10)
                    char.hp = min(char.hp, char.max_hp)
                    metrics.gold_spent_training += 50
                    metrics.training_sessions += 1
                    metrics.stats_trained[attr] += 1
            # Upgrade weapon if needed and affordable
            weapon_dict = SmartAI.should_buy_weapon(char, self.weapons)
            if weapon_dict and char.gold >= weapon_dict.get(
                "price", weapon_dict.get("cost", 0)
            ):
                cost = weapon_dict.get("price", weapon_dict.get("cost", 0))
                char.gold -= cost
                weapon = Weapon(
                    name=weapon_dict["name"], damage_die=weapon_dict["damage_die"]
                )
                char.weapons = [weapon]
                metrics.gold_spent_weapons += cost
                metrics.weapons_bought += 1
            # Upgrade armor if needed and affordable
            armor_dict = SmartAI.should_buy_armor(char, self.armors)
            if armor_dict and char.gold >= armor_dict.get(
                "price", armor_dict.get("cost", 0)
            ):
                cost = armor_dict.get("price", armor_dict.get("cost", 0))
                char.gold -= cost
                armor = Armor(
                    name=armor_dict["name"], armor_class=armor_dict["armor_class"]
                )
                char.armor = armor
                metrics.gold_spent_armor += cost
                metrics.armor_bought += 1
            # Buy potions if low (keep 3-5 in stock)
            if char.potions < 3 and char.gold >= 20:
                potions_to_buy = min(3 - char.potions, char.gold // 20)
                if potions_to_buy > 0:
                    char.potions += potions_to_buy
                    cost = potions_to_buy * 20
                    char.gold -= cost
                    metrics.gold_spent_potions += cost
                    metrics.potions_bought += potions_to_buy

    def combat_turn(
        self,
        char: Character,
        monster: Monster,
        metrics: SimulationMetrics,
        examined_this_combat: bool,
    ) -> Tuple[bool, bool, bool]:
        """
        Execute one turn of combat.
        Returns: (char_won, char_died, examined_this_turn)
        """
        # Dragon policy: always attack (no examine/divine), but still use potion at 50%
        if (monster.name or "").lower() == "dragon":
            if SmartAI.should_use_potion(char, monster.hp):
                if char.potions > 0:
                    con = char.attributes.get("Constitution", 10)
                    mult = max(1, math.ceil(con / 2))
                    heal = sum(max(1, roll_damage("2d2")) for _ in range(mult))
                    char.hp = min(char.max_hp, char.hp + heal)
                    char.potions -= 1
                    metrics.potions_used += 1
                    # Monster attacks after potion
                    return self.monster_attacks(char, monster, metrics)
            # Always attack vs Dragon
            return self.player_attacks(char, monster, metrics)

        # Check if we should examine (once per combat, doesn't trigger monster attack)
        if SmartAI.should_examine(char, monster, examined_this_combat):
            wis = char.attributes.get("Wisdom", 10)
            roll = roll_damage("5d4") + wis
            metrics.examine_used += 1
            if roll > 25:
                # Success: we now know monster stats
                pass
            # Examine doesn't trigger monster attack - return to our turn
            return False, False, True

        # Check if we should use potion (before attacking)
        if SmartAI.should_use_potion(char, monster.hp):
            if char.potions > 0:
                con = char.attributes.get("Constitution", 10)
                mult = max(1, math.ceil(con / 2))
                heal = sum(max(1, roll_damage("2d2")) for _ in range(mult))
                char.hp = min(char.max_hp, char.hp + heal)
                char.potions -= 1
                metrics.potions_used += 1
                # Potion consumes turn - monster attacks
                return self.monster_attacks(char, monster, metrics)

        # Check if we should use divine (desperate situations only)
        if SmartAI.should_use_divine(char, monster):
            wis = char.attributes.get("Wisdom", 10)
            roll = roll_damage("5d4") + (wis - 10)
            metrics.divine_used += 1

            if roll >= 12:
                # Success: deal damage
                die = "4d6" if roll >= 16 else "3d6"
                dmg = max(1, roll_damage(die))
                monster.hp -= dmg
                metrics.damage_dealt += dmg
                metrics.divine_success += 1

                if monster.hp <= 0:
                    metrics.monsters_killed += 1
                    return True, False, examined_this_combat

            # Divine ALWAYS triggers monster attack (even on success)
            return self.monster_attacks(char, monster, metrics)

        # Normal attack
        return self.player_attacks(char, monster, metrics)

    def player_attacks(
        self, char: Character, monster: Monster, metrics: SimulationMetrics
    ) -> Tuple[bool, bool, bool]:
        """Player attacks monster, then monster counterattacks"""
        metrics.total_attacks += 1

        # Roll attack
        attack_die = roll_damage("5d4")
        str_mod = char.attributes.get("Strength", 10)
        attack_roll = attack_die + str_mod

        # Zone combat (simplified: 33% chance monster blocks)
        blocked = random.random() < 0.33

        # Fumble (minimum roll)
        if attack_die == 5:
            self_dmg = max(1, roll_damage("1d4"))
            char.hp -= self_dmg
            metrics.damage_taken += self_dmg
            metrics.attacks_missed += 1

            if char.hp <= 0:
                return False, True, False

            # Monster still attacks after fumble
            return self.monster_attacks(char, monster, metrics)

        # Check if blocked
        if blocked and attack_die != 20:
            metrics.attacks_blocked += 1
            # Monster attacks after block
            return self.monster_attacks(char, monster, metrics)

        # Check if hit
        if attack_roll >= monster.armor_class or attack_die == 20:
            # Calculate damage
            weapon = char.weapons[0] if char.weapons else None
            if weapon:
                base_dmg = roll_damage(weapon.damage_die)
            else:
                base_dmg = 2  # Unarmed

            str_bonus = math.ceil(str_mod / 2)
            dmg = max(1, base_dmg + str_bonus)

            # Critical hit (natural 20)
            if attack_die == 20:
                dmg = int(dmg * 1.5)
                metrics.critical_hits += 1

            monster.hp -= dmg
            metrics.damage_dealt += dmg
            metrics.attacks_hit += 1

            if monster.hp <= 0:
                metrics.monsters_killed += 1
                return True, False, False
        else:
            metrics.attacks_missed += 1

        # Monster counterattacks
        return self.monster_attacks(char, monster, metrics)

    def monster_attacks(
        self, char: Character, monster: Monster, metrics: SimulationMetrics
    ) -> Tuple[bool, bool, bool]:
        """Monster attacks player"""
        # Monster attack roll
        attack_die = roll_damage("5d4")
        monster_str = getattr(monster, "strength", 10)
        attack_roll = attack_die + (monster_str // 2)

        char_ac = compute_armor_class(char)

        # Zone blocking (simplified: 33% chance player blocks)
        blocked = random.random() < 0.33

        # Monster fumble
        if attack_die == 5:
            self_dmg = max(1, roll_damage(monster.damage_die))
            monster.hp -= self_dmg
            if monster.hp <= 0:
                metrics.monsters_killed += 1
                return True, False, False
            return False, False, False

        # Check if blocked
        if blocked and attack_die != 20:
            return False, False, False

        # Check if hit
        if attack_roll >= char_ac or attack_die == 20:
            dmg = max(1, roll_damage(monster.damage_die))

            if attack_die == 20:
                dmg = int(dmg * 1.5)

            char.hp -= dmg
            metrics.damage_taken += dmg

            if char.hp <= 0:
                try:
                    metrics.death_reasons[monster.name] += 1
                except Exception:
                    pass
                return False, True, False

        return False, False, False

    def attempt_revival(self, char: Character, metrics: SimulationMetrics) -> bool:
        """Attempt to revive character after death"""
        metrics.deaths += 1
        death_count = getattr(char, "death_count", 0) + 1
        setattr(char, "death_count", death_count)

        wis = char.attributes.get("Wisdom", 10)
        roll = roll_damage("5d4") + wis
        dc = 15 + 5 * death_count

        if roll >= dc:
            # Revival success
            metrics.revivals += 1

            # Apply penalties (-1 to all stats, min 3)
            for attr in [
                "Strength",
                "Dexterity",
                "Constitution",
                "Intelligence",
                "Wisdom",
                "Charisma",
                "Perception",
            ]:
                char.attributes[attr] = max(3, char.attributes.get(attr, 10) - 1)

            char.hp = 1
            char.max_hp = 10 + char.attributes.get("Constitution", 10)

            return True
        else:
            # Permanent death
            metrics.permanent_death = True
            return False

    def run_character(
        self, char_num: int, difficulty: str = "normal"
    ) -> SimulationMetrics:
        """Run a complete character from creation to death or victory"""
        metrics = SimulationMetrics()

        # Create character
        char = Character(name=f"Hero_{char_num}", clazz="Warrior", max_hp=1, gold=0)
        # Roll and allocate stats per engine difficulty dice
        dice = self._stat_dice_for_difficulty(difficulty)
        rolls = [roll_damage(dice) for _ in range(7)]
        SmartAI.allocate_stats_smart(char, rolls)

        metrics.character_name = char.name
        metrics.starting_stats = dict(char.attributes)

        # Starting HP per engine: base_hp = 3*CON + roll(5d4)
        con = int(char.attributes.get("Constitution", 10))
        base_hp = 3 * con
        hp_bonus = roll_damage("5d4")
        char.max_hp = base_hp + hp_bonus
        char.hp = char.max_hp

        # Starting gold per engine: 20d6 + ceil(CHA/1.5)d6 + low-HP bonus (tiers)
        base_gold = roll_damage("20d6")
        cha = int(char.attributes.get("Charisma", 10))
        cha_dice = int(math.ceil(cha / 1.5))
        cha_bonus = roll_damage(f"{cha_dice}d6") if cha_dice > 0 else 0
        # Low HP bonus tiers (apply highest matching)
        hp = char.max_hp
        hp_bonus_die = None
        if hp < 25:
            hp_bonus_die = "15d6"
        elif hp < 30:
            hp_bonus_die = "10d6"
        elif hp < 40:
            hp_bonus_die = "7d6"
        elif hp < 50:
            hp_bonus_die = "5d6"
        elif hp < 60:
            hp_bonus_die = "3d6"
        low_hp_bonus = roll_damage(hp_bonus_die) if hp_bonus_die else 0
        char.gold = base_gold + cha_bonus + low_hp_bonus

        # Initial town visit (buy starting gear)
        self.town_phase(char, metrics, first_visit=True)

        # Main game loop
        current_depth = 1
        encounter_count = 0
        just_revived = False
        deep_shop_done = False

        while char.hp > 0 and encounter_count < 100:  # Safety limit
            metrics.total_turns += 1

            # Check if should visit town (after revival or pre-deep push)
            if SmartAI.should_visit_town(char, current_depth, just_revived):
                self.town_phase(char, metrics, first_visit=False)
                if just_revived:
                    current_depth = 1
                    deep_shop_done = False
                just_revived = False

            # Before pushing into depth 4/5, return to town to gear up if we can afford basics
            if (not deep_shop_done) and current_depth >= 4:
                can_afford_basics = (
                    (char.gold >= 40)
                    or (char.gold >= 60)
                    or (char.potions < 3 and char.gold >= 20)
                )
                if can_afford_basics:
                    self.town_phase(char, metrics, first_visit=False)
                    deep_shop_done = True

            # Dragon spawns at 50th encounter OR at depth 5
            if encounter_count >= 50 or current_depth >= 5:
                monster = self.create_monster("Dragon", current_depth)
                metrics.dragon_encountered = True
            else:
                monster = self.create_monster(depth=current_depth)

            # Track unique monsters faced
            try:
                metrics.unique_monsters.add(monster.name)
            except Exception:
                pass

            metrics.total_encounters += 1
            encounter_count += 1

            # No pre-combat gold; rewards are granted on victory based on monsters.json (depth-scaled)

            # Combat loop
            examined_this_combat = False
            combat_turns = 0
            max_combat_turns = 50  # Prevent infinite loops

            while char.hp > 0 and monster.hp > 0 and combat_turns < max_combat_turns:
                char_won, char_died, examined = self.combat_turn(
                    char, monster, metrics, examined_this_combat
                )

                if examined:
                    examined_this_combat = True
                    continue  # Examine doesn't end turn

                combat_turns += 1

                if char_won:
                    # Victory!
                    if char_won:
                        # Victory! Award XP and gold based on monsters.json with depth scaling
                        try:
                            entry = next(
                                (
                                    m
                                    for m in self.monsters_data
                                    if m.get("name") == monster.name
                                ),
                                None,
                            )
                            depth = max(1, current_depth)
                            # XP award
                            base_xp = int(entry.get("xp", 10)) if entry else 10
                            xp_reward = max(0, int(base_xp * depth))
                            _ = char.gain_xp(xp_reward)
                            # Auto-spend stat points: STR then CON
                            while getattr(char, "unspent_stat_points", 0) > 0:
                                if char.attributes.get("Strength", 10) < 20:
                                    char.attributes["Strength"] = (
                                        char.attributes.get("Strength", 10) + 1
                                    )
                                    char.unspent_stat_points -= 1
                                    metrics.stats_trained["Strength"] += 1
                                    metrics.training_sessions += 1
                                elif char.attributes.get("Constitution", 10) < 20:
                                    char.attributes["Constitution"] = (
                                        char.attributes.get("Constitution", 10) + 1
                                    )
                                    char.max_hp += 5
                                    char.unspent_stat_points -= 1
                                    metrics.stats_trained["Constitution"] += 1
                                    metrics.training_sessions += 1
                                else:
                                    break
                            # Gold award
                            base_gold = None
                            if (
                                entry
                                and isinstance(entry.get("gold_range"), list)
                                and len(entry["gold_range"]) == 2
                            ):
                                lo, hi = int(entry["gold_range"][0]), int(
                                    entry["gold_range"][1]
                                )
                                if hi < lo:
                                    lo, hi = hi, lo
                                base_gold = random.randint(lo, hi)
                            if base_gold is None:
                                base_gold = 0
                            gold_reward = max(0, int(base_gold * depth))
                            char.gold += gold_reward
                            metrics.gold_earned += gold_reward
                        except Exception:
                            pass

                        if monster.name == "Dragon":
                            # WON THE GAME!
                            metrics.won_game = True
                            metrics.final_stats = dict(char.attributes)
                            metrics.final_hp = char.hp
                            metrics.final_max_hp = char.max_hp
                            metrics.final_gold = char.gold
                            metrics.max_depth_reached = max(
                                metrics.max_depth_reached, current_depth
                            )
                            return metrics

                        # Regular monster defeated - go deeper (max 5)
                        current_depth = min(5, current_depth + 1)
                        metrics.max_depth_reached = max(
                            metrics.max_depth_reached, current_depth
                        )
                        # Quests turn-in for kill (if available)
                        try:
                            from game.quests import quest_manager
                            from game.entities import Monster as _EM

                            mobj = _EM(
                                name=monster.name,
                                hp=max(0, monster.hp),
                                armor_class=monster.armor_class,
                                damage_die=monster.damage_die,
                            )
                            changed = quest_manager.check_kill(char, mobj)
                            if changed:
                                metrics.quests_completed += len(changed)
                        except Exception:
                            pass
                        break

                if char_died:
                    # Attempt revival
                    if self.attempt_revival(char, metrics):
                        just_revived = True
                        break
                    else:
                        # Permanent death
                        metrics.final_stats = dict(char.attributes)
                        metrics.final_hp = 0
                        metrics.final_max_hp = char.max_hp
                        metrics.final_gold = char.gold
                        return metrics

        # Shouldn't reach here, but handle it
        metrics.final_stats = dict(char.attributes)
        metrics.final_hp = char.hp
        metrics.final_max_hp = char.max_hp
        metrics.final_gold = char.gold
        return metrics


def run_simulation(
    num_characters: int = 100, difficulty: str = "normal", verbose: bool = True
) -> List[SimulationMetrics]:
    """Run simulation for multiple characters"""
    simulator = GameSimulator()
    results = []

    print(
        f"Starting simulation of {num_characters} characters (difficulty={difficulty})..."
    )
    print("=" * 60)

    for i in range(num_characters):
        if verbose and (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{num_characters} characters completed")

        metrics = simulator.run_character(i + 1, difficulty=difficulty)
        results.append(metrics)

        # Show individual result if verbose
        if verbose:
            outcome = (
                "VICTORY (Dragon Slain!)" if metrics.won_game else "Permanent Death"
            )
            print(
                f"  {metrics.character_name}: {outcome} - "
                f"Encounters: {metrics.total_encounters}, "
                f"Max Depth: {metrics.max_depth_reached}, "
                f"Kills: {metrics.monsters_killed}"
            )

    print("=" * 60)
    print("Simulation complete!")
    return results


def analyze_results(results: List[SimulationMetrics]):
    """Generate comprehensive analysis"""

    total = len(results)
    victories = sum(1 for r in results if r.won_game)
    deaths = sum(1 for r in results if r.permanent_death)

    print("\n" + "=" * 60)
    print("SIMULATION RESULTS - 100 CHARACTER RUNS")
    print("=" * 60)

    print(f"\n=== OUTCOMES ===")
    print(f"Total Characters: {total}")
    print(f"VICTORIES (Dragon Slain): {victories} ({victories/total*100:.1f}%)")
    print(f"Permanent Deaths: {deaths} ({deaths/total*100:.1f}%)")
    print(
        f"Dragon Encountered: {sum(1 for r in results if r.dragon_encountered)} ({sum(1 for r in results if r.dragon_encountered)/total*100:.1f}%)"
    )

    print(f"\n=== PROGRESSION ===")
    print(f"Total Encounters: {sum(r.total_encounters for r in results):,}")
    print(
        f"Average Encounters per Character: {sum(r.total_encounters for r in results)/total:.1f}"
    )
    print(f"Total Turns: {sum(r.total_turns for r in results):,}")
    print(
        f"Average Turns per Character: {sum(r.total_turns for r in results)/total:.1f}"
    )
    print(f"Average Max Depth: {sum(r.max_depth_reached for r in results)/total:.2f}")
    print(f"Deepest Depth Reached: {max(r.max_depth_reached for r in results)}")
    # Unique monsters faced stats
    try:
        avg_unique = (
            sum(len(getattr(r, "unique_monsters", set())) for r in results) / total
        )
        print(f"Average Unique Monsters Faced: {avg_unique:.1f}")
    except Exception:
        pass

    print(f"\n=== COMBAT PERFORMANCE ===")
    total_attacks = sum(r.total_attacks for r in results)
    total_hits = sum(r.attacks_hit for r in results)
    total_misses = sum(r.attacks_missed for r in results)
    total_blocked = sum(r.attacks_blocked for r in results)
    total_crits = sum(r.critical_hits for r in results)

    print(f"Total Attacks: {total_attacks:,}")
    print(f"Hits: {total_hits:,} ({total_hits/total_attacks*100:.1f}%)")
    print(f"Misses: {total_misses:,} ({total_misses/total_attacks*100:.1f}%)")
    print(f"Blocked: {total_blocked:,} ({total_blocked/total_attacks*100:.1f}%)")
    print(f"Critical Hits: {total_crits:,} ({total_crits/total_attacks*100:.1f}%)")

    total_kills = sum(r.monsters_killed for r in results)
    total_encounters = sum(r.total_encounters for r in results)
    print(f"\nMonsters Killed: {total_kills:,}")
    print(
        f"Average Turns per Monster: {total_attacks/total_kills:.1f}"
        if total_kills > 0
        else "N/A"
    )

    print(f"\n=== DAMAGE ===")
    print(f"Total Damage Dealt: {sum(r.damage_dealt for r in results):,}")
    print(f"Total Damage Taken: {sum(r.damage_taken for r in results):,}")
    print(
        f"Average Damage per Encounter (Dealt): {sum(r.damage_dealt for r in results)/total_encounters:.1f}"
    )
    print(
        f"Average Damage per Encounter (Taken): {sum(r.damage_taken for r in results)/total_encounters:.1f}"
    )

    print(f"\n=== DEATHS & REVIVALS ===")
    print(f"Total Deaths: {sum(r.deaths for r in results)}")
    print(f"Total Revivals: {sum(r.revivals for r in results)}")
    print(f"Average Deaths per Character: {sum(r.deaths for r in results)/total:.2f}")
    print(
        f"Average Revivals per Character: {sum(r.revivals for r in results)/total:.2f}"
    )
    # Aggregate death reasons
    all_reasons = defaultdict(int)
    for r in results:
        for k, v in getattr(r, "death_reasons", {}).items():
            all_reasons[k] += v
    if all_reasons:
        print("Death Reasons (top 5):")
        for name, count in sorted(
            all_reasons.items(), key=lambda kv: kv[1], reverse=True
        )[:5]:
            print(f"  {name}: {count}")

    print(f"\n=== ACTION USAGE ===")
    print(f"Divine Aid Used: {sum(r.divine_used for r in results):,}")
    divine_total = sum(r.divine_used for r in results)
    divine_success = sum(r.divine_success for r in results)
    print(
        f"Divine Success Rate: {divine_success/divine_total*100:.1f}%"
        if divine_total > 0
        else "N/A"
    )
    print(f"Examine Used: {sum(r.examine_used for r in results):,}")
    print(f"Potions Used: {sum(r.potions_used for r in results):,}")
    print(f"Spells Cast: {sum(r.spells_cast for r in results):,}")

    print(f"\n=== ECONOMY ===")
    print(f"Total Gold Earned: {sum(r.gold_earned for r in results):,}g")
    print(f"Average Gold Earned: {sum(r.gold_earned for r in results)/total:.0f}g")
    print(f"\nGold Spent:")
    print(f"  Weapons: {sum(r.gold_spent_weapons for r in results):,}g")
    print(f"  Armor: {sum(r.gold_spent_armor for r in results):,}g")
    print(f"  Potions: {sum(r.gold_spent_potions for r in results):,}g")
    print(f"  Training: {sum(r.gold_spent_training for r in results):,}g")
    print(
        f"  Total Spent: {sum(r.gold_spent_weapons + r.gold_spent_armor + r.gold_spent_potions + r.gold_spent_training for r in results):,}g"
    )

    print(f"\n=== PURCHASES ===")
    print(f"Weapons Bought: {sum(r.weapons_bought for r in results)}")
    print(f"Armor Bought: {sum(r.armor_bought for r in results)}")
    print(f"Potions Bought: {sum(r.potions_bought for r in results)}")

    print(f"\n=== TRAINING ===")
    print(f"Training Sessions: {sum(r.training_sessions for r in results)}")

    # Aggregate training stats
    all_training = defaultdict(int)
    for r in results:
        for attr, count in r.stats_trained.items():
            all_training[attr] += count

    total_training = sum(all_training.values())
    if total_training > 0:
        print(f"Training Distribution:")
        for attr in [
            "Strength",
            "Constitution",
            "Dexterity",
            "Wisdom",
            "Intelligence",
            "Charisma",
            "Perception",
        ]:
            count = all_training.get(attr, 0)
            pct = count / total_training * 100
            print(f"  {attr}: {count} ({pct:.1f}%)")

    print(f"\n=== TOWN VISITS ===")
    print(f"Total Town Visits: {sum(r.town_visits for r in results)}")
    print(f"Average per Character: {sum(r.town_visits for r in results)/total:.1f}")

    print(f"\n=== VICTORY ANALYSIS ===")
    if victories > 0:
        victory_chars = [r for r in results if r.won_game]
        print(f"Victorious Characters: {len(victory_chars)}")
        print(
            f"Average Starting STR: {sum(r.starting_stats.get('Strength', 10) for r in victory_chars)/len(victory_chars):.1f}"
        )
        print(
            f"Average Starting CON: {sum(r.starting_stats.get('Constitution', 10) for r in victory_chars)/len(victory_chars):.1f}"
        )
        print(
            f"Average Final STR: {sum(r.final_stats.get('Strength', 10) for r in victory_chars)/len(victory_chars):.1f}"
        )
        print(
            f"Average Final CON: {sum(r.final_stats.get('Constitution', 10) for r in victory_chars)/len(victory_chars):.1f}"
        )
        print(
            f"Average Encounters to Victory: {sum(r.total_encounters for r in victory_chars)/len(victory_chars):.1f}"
        )
        print(
            f"Average Gold at Victory: {sum(r.final_gold for r in victory_chars)/len(victory_chars):.0f}g"
        )
    else:
        print("No victories achieved in this simulation.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run simulation
    results = run_simulation(100)

    # Analyze and display results
    analyze_results(results)

    # Save detailed results to file
    output_file = "simulation_results_FIXED.txt"
    with open(output_file, "w") as f:
        f.write("DETAILED SIMULATION RESULTS\n")
        f.write("=" * 60 + "\n\n")

        for r in results:
            outcome = "VICTORY" if r.won_game else "DEATH"
            f.write(f"\n{r.character_name} - {outcome}\n")
            f.write(
                f"  Starting Stats: STR {r.starting_stats.get('Strength', 10)} "
                f"CON {r.starting_stats.get('Constitution', 10)} "
                f"DEX {r.starting_stats.get('Dexterity', 10)}\n"
            )
            f.write(
                f"  Encounters: {r.total_encounters}, Max Depth: {r.max_depth_reached}\n"
            )
            f.write(
                f"  Kills: {r.monsters_killed}, Deaths: {r.deaths}, Revivals: {r.revivals}\n"
            )
            f.write(f"  Hit Rate: {r.hit_rate():.1f}%\n")
            f.write(f"  Gold Earned: {r.gold_earned}g, Final: {r.final_gold}g\n")
            f.write(f"  Potions Used: {r.potions_used}, Divine Used: {r.divine_used}\n")

    print(f"\nDetailed results saved to: {output_file}")
