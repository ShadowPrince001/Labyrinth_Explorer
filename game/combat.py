from .dice import roll_damage
from .entities import Character, Monster
from .companion import summon_companion, companion_turn
from .data_loader import get_dialogue, load_monster_descriptions, get_npc_dialogue
import random
import math


class TeleportToTown(Exception):
    pass


def compute_armor_class(character: Character, ac_bonus: int = 0) -> int:
    # Base AC = 10 + Constitution/2 (rounded up) to match new mechanics
    constitution = character.attributes.get("Constitution", 10)
    base_ac = 10 + math.ceil(constitution / 2)

    # Add armor AC
    armor_ac = 0
    if character.armor:
        # Damaged armor provides reduced protection (half armor AC)
        armor_ac = (
            character.armor.armor_class // 2
            if getattr(character.armor, "damaged", False)
            else character.armor.armor_class
        )

    return base_ac + armor_ac + ac_bonus


def wisdom_bonus(character: Character) -> int:
    wis = character.attributes.get("Wisdom", 10)
    return 2 if wis >= 15 else (1 if wis >= 12 else 0)


def examine_monster(character: Character, monster: Monster) -> bool:
    """Examine monster with 5d4 + wisdom > 25 check. Returns True if successful."""
    wis = character.attributes.get("Wisdom", 10)
    roll = roll_damage("5d4") + wis
    intro = (
        get_dialogue("combat", "examine_attempt", None, character)
        or f"You examine the {monster.name}..."
    )
    intro_line = (intro + " (Wisdom check: {roll} vs 25)") if intro else None
    print(
        (
            get_dialogue("combat", "examine_intro", None, character)
            or intro_line
            or f"You examine the {monster.name}... (Wisdom check: {roll} vs 25)"
        ).format(roll=roll)
    )
    if roll > 25:
        hp_line = (
            get_dialogue("combat", "examine_result", None, character)
            or "You can see: HP {hp}, AC {ac}"
        )
        print(hp_line.format(hp=monster.hp, ac=monster.armor_class))
        if hasattr(monster, "dexterity"):
            dex_line = (
                get_dialogue("combat", "examine_dex", None, character)
                or "Dexterity: {dex}"
            )
            print(dex_line.format(dex=monster.dexterity))
        if hasattr(monster, "abilities") and monster.abilities:
            abil_line = (
                get_dialogue("combat", "examine_abilities", None, character)
                or "Special abilities: {abilities}"
            )
            print(abil_line.format(abilities=", ".join(monster.abilities)))
        # Also show a textual description for the monster if available in data/monsters_desc.json
        try:
            desc_map = load_monster_descriptions() or {}
            # Normalized lookup: prefer exact name, fall back to title-cased name
            desc = desc_map.get(monster.name) or desc_map.get(str(monster.name).title())
            if desc:
                # Print a concise description using monster name and the description text
                print(f"It's a {monster.name} - {desc}")
        except Exception:
            # If description loading fails for any reason, skip silently
            pass
        # Also show a textual description for the monster if available in data/monsters_desc.json
        try:
            desc_map = load_monster_descriptions() or {}
            # Normalized lookup: prefer exact name, fall back to title-cased name
            desc = desc_map.get(monster.name) or desc_map.get(str(monster.name).title())
            if desc:
                # Print a concise description using monster name and the description text
                print(f"It's a {monster.name} - {desc}")
        except Exception:
            # If description loading fails for any reason, skip silently
            pass
        return True  # Successful examine
    else:
        print(
            get_dialogue("combat", "examine_fail", None, character)
            or "You can't make out the creature's capabilities clearly."
        )
        return False  # Failed examine


def choose_weapon(character: Character):
    if not character.weapons:
        return None
    if len(character.weapons) == 1:
        return character.weapons[0]
    print(get_dialogue("combat", "choose_weapon", None, character) or "Choose weapon:")
    for idx, w in enumerate(character.weapons, start=1):
        opt = (
            get_dialogue("combat", "weapon_option", None, character)
            or "{idx}) {name} ({damage} damage)"
        )
        print(opt.format(idx=idx, name=w.name, damage=w.damage_die))
    print(get_dialogue("system", "enter_number", None, character) or ">")
    choice = input("> ").strip()
    try:
        index = int(choice) - 1
        return character.weapons[index]
    except Exception:
        return character.weapons[0]


def use_potion(character: Character, buffs: dict) -> bool:
    # List available potions by name with remaining uses
    available = {name: uses for name, uses in character.potion_uses.items() if uses > 0}
    if not available and character.potions <= 0:
        print(
            get_dialogue("combat", "no_potions", None, character)
            or "You have no potions."
        )
        return False
    print(
        "\n"
        + (
            get_dialogue("combat", "potions_menu", None, character)
            or "Potions (choose by number):"
        )
    )
    options = []
    idx = 1
    # Legacy healing
    if character.potions > 0:
        opt = (
            get_dialogue("combat", "potion_option", None, character) or "{idx}) {label}"
        )
        print(opt.format(idx=idx, label="Healing (legacy) (1 use)"))
        options.append((idx, ("Healing_legacy", 1)))
        idx += 1
    for name, uses in available.items():
        opt = (
            get_dialogue("combat", "potion_option", None, character)
            or "{idx}) {label} ({uses} uses left)"
        )
        print(opt.format(idx=idx, label=name, uses=uses))
        options.append((idx, (name, uses)))
        idx += 1
    print(get_dialogue("system", "enter_number", None, character) or ">")
    choice = input("> ").strip()
    if not choice.isdigit():
        return False
    sel = int(choice)
    match = next((x for x in options if x[0] == sel), None)
    if not match:
        return False
    name, uses = match[1]
    # Apply effects
    if name == "Healing_legacy" or name.lower() == "healing":
        # Heal 2d4
        heal = max(1, roll_damage("2d4"))
        character.hp = min(character.max_hp, character.hp + heal)
        print(
            get_dialogue("combat", "potion_heal", None, character)
            or f"You drink a healing potion and recover {heal} HP."
        )
        if name == "Healing_legacy":
            character.potions -= 1
        else:
            character.potion_uses[name] -= 1
        return True
    elif name.lower() == "intelligence":
        buffs["damage_bonus"] = buffs.get("damage_bonus", 0) + 1
        character.potion_uses[name] -= 1
        print(
            get_dialogue("combat", "potion_focus", None, character)
            or "You feel more focused. (+1 damage this combat)"
        )
        return True
    elif name.lower() == "speed":
        buffs["extra_attack_charges"] = buffs.get("extra_attack_charges", 0) + 1
        character.potion_uses[name] -= 1
        print(
            get_dialogue("combat", "potion_speed", None, character)
            or "Your reflexes quicken. (1 extra attack this combat)"
        )
        return True
    elif name.lower() == "strength":
        buffs["damage_bonus"] = buffs.get("damage_bonus", 0) + 2
        character.potion_uses[name] -= 1
        print(
            get_dialogue("combat", "potion_strength", None, character)
            or "Your muscles surge. (+2 damage this combat)"
        )
        return True
    elif name.lower() == "protection":
        buffs["ac_bonus"] = buffs.get("ac_bonus", 0) + 3
        character.potion_uses[name] -= 1
        print(
            get_dialogue("combat", "potion_protection", None, character)
            or "A shimmering barrier surrounds you. (+3 AC this combat)"
        )
        return True
    elif name.lower() == "invisibility":
        buffs["invisibility_charges"] = buffs.get("invisibility_charges", 0) + 1
        character.potion_uses[name] -= 1
        print(
            get_dialogue("combat", "potion_invisibility", None, character)
            or "You fade from sight. (Monster's next attack automatically misses)"
        )
        return True
    elif name.lower() == "antidote":
        character.potion_uses[name] -= 1
        character.persistent_buffs.pop("debuff_poison", None)
        print(
            get_dialogue("combat", "potion_antidote", None, character)
            or "You drink the antidote and feel the poison leave your system."
        )
        return True
    else:
        print(
            get_dialogue("combat", "nothing_happens", None, character)
            or "Nothing happens..."
        )
        return False


def cast_spell(
    character: Character, monster: Monster, buffs: dict, enemy_debuffs: dict
) -> bool:
    available = {name: uses for name, uses in character.spells.items() if uses > 0}
    if not available:
        print(
            get_dialogue("combat", "no_spells", None, character)
            or "You don't know any spells."
        )
        return False
    print(
        "\n"
        + (
            get_dialogue("combat", "spells_menu", None, character)
            or "Spells (choose by number):"
        )
    )
    options = []
    idx = 1
    for name, uses in available.items():
        opt = (
            get_dialogue("combat", "spell_option", None, character)
            or "{idx}) {label} ({uses} uses left)"
        )
        print(opt.format(idx=idx, label=name, uses=uses))
        options.append((idx, name))
        idx += 1
    print(get_dialogue("system", "enter_number", None, character) or ">")
    choice = input("> ").strip()
    if not choice.isdigit():
        return False
    sel = int(choice)
    match = next((x for x in options if x[0] == sel), None)
    if not match:
        return False
    name = match[1]
    lname = name.lower()
    resist = enemy_debuffs.get("spell_resistance", 0)

    def apply_resist(dmg: int) -> int:
        return max(0, dmg - resist)

    if lname == "summon creature":
        roll = roll_damage("5d4")
        print(
            get_dialogue("combat", "summon_attempt", None, character)
            or f"You attempt to summon a companion... Roll {roll}"
        )
        ok = summon_companion(character, roll)
        if ok:
            character.spells[name] -= 1
            return True
        else:
            return False
    if lname == "magic missile":
        dmg = apply_resist(max(1, roll_damage("2d6")))
        monster.hp -= dmg
        print(
            get_dialogue("combat", "magic_missile", None, character)
            or f"Magic missiles strike for {dmg} damage. Monster HP: {max(monster.hp, 0)}"
        )
    elif lname == "weakness":
        enemy_debuffs["damage_penalty"] = enemy_debuffs.get("damage_penalty", 0) + 2
        print(
            get_dialogue("combat", "weakness_effect", None, character)
            or "The foe looks feebler. (-2 damage this combat)"
        )
    elif lname == "slowness":
        enemy_debuffs["damage_penalty"] = enemy_debuffs.get("damage_penalty", 0) + 2
        print(
            get_dialogue("combat", "slowness_effect", None, character)
            or "The foe slows. (-2 damage this combat)"
        )
    elif lname == "lightning bolt":
        print(
            get_dialogue("combat", "choose_aim", None, character)
            or "Choose power level:"
        )
        print(
            get_dialogue("combat", "full_power_option", None, character)
            or "1) Full power"
        )
        print(
            get_dialogue("combat", "half_power_option", None, character)
            or "2) Half power"
        )
        print(get_dialogue("system", "enter_number", None, character) or ">")
        mode = input("> ").strip()
        die = "6d6" if mode == "1" else "3d6"
        dmg = apply_resist(max(1, roll_damage(die)))
        monster.hp -= dmg
        print(
            get_dialogue("combat", "lightning_bolt", None, character)
            or f"Lightning arcs for {dmg} damage. Monster HP: {max(monster.hp, 0)}"
        )
    elif lname == "freeze":
        enemy_debuffs["freeze_turns"] = enemy_debuffs.get("freeze_turns", 0) + 1
        print(
            get_dialogue("combat", "freeze_effect", None, character)
            or "Ice binds the monster. (It skips its next turn)"
        )
    elif lname == "vulnerability":
        enemy_debuffs["ac_penalty"] = enemy_debuffs.get("ac_penalty", 0) + 2
        print(
            get_dialogue("combat", "vulnerability_effect", None, character)
            or "Cracks appear in its defenses. (-2 AC this combat)"
        )
    elif lname == "fireball":
        dmg = apply_resist(max(1, roll_damage("4d6")))
        monster.hp -= dmg
        print(
            get_dialogue("combat", "fireball", None, character)
            or f"Fireball explodes for {dmg} damage. Monster HP: {max(monster.hp, 0)}"
        )
    elif lname == "teleport to town":
        print(
            get_dialogue("combat", "teleport_to_town", None, character)
            or "A portal whisks you away to town!"
        )
        character.spells[name] -= 1
        raise TeleportToTown()
    elif lname == "magic portal":
        print(
            get_dialogue("combat", "magic_portal", None, character)
            or "You conjure a portal and step through to safety."
        )
        character.spells[name] -= 1
        raise TeleportToTown()
    else:
        print(
            get_dialogue("combat", "spell_fizzle", None, character)
            or "The spell fizzles..."
        )
        return False
    character.spells[name] -= 1
    return True


def choose_aim_zone(character: Character = None) -> str:
    # character is optional for UI flavor; allow calling without passing character
    print(get_dialogue("combat", "choose_aim", None, character) or "Aim your attack:")
    print(get_dialogue("combat", "height_options", None, character))
    print(get_dialogue("system", "enter_number", None, character) or ">")
    choice = input("> ").strip()
    return _normalize_zone_input(choice)


def choose_defend_zone(character: Character = None) -> str:
    # character is optional for UI flavor; allow calling without passing character
    print(
        get_dialogue("combat", "choose_defend", None, character)
        or "Choose defense zone:"
    )
    print(get_dialogue("combat", "height_options", None, character))
    print(get_dialogue("system", "enter_number", None, character) or ">")
    choice = input("> ").strip()
    return _normalize_zone_input(choice)


def _normalize_zone_input(choice: str) -> str:
    """Normalize various user inputs (numbers, words, or labels) to canonical zones:
    'high', 'middle', or 'low'. Accepts numeric choices like '1'/'2'/'3', words like
    'upper', 'center', 'lower', or full labels like '1) Head/Upper'. Defaults to 'middle'.
    """
    if not choice:
        return "middle"
    import re

    s = choice.strip().lower()
    # If user clicked a numbered button, try to extract leading digit
    m = re.match(r"\s*([1-3])\b", s)
    if m:
        map_digit = {"1": "high", "2": "middle", "3": "low"}
        return map_digit.get(m.group(1), "middle")
    # Check for common synonyms
    if any(x in s for x in ("high", "upper", "head", "top", "crown")):
        return "high"
    if any(x in s for x in ("middle", "centre", "center", "torso", "mid", "heart")):
        return "middle"
    if any(x in s for x in ("low", "lower", "legs", "feet", "bottom")):
        return "low"
    # Also accept raw digits anywhere
    m2 = re.search(r"([1-3])", s)
    if m2:
        return {"1": "high", "2": "middle", "3": "low"}.get(m2.group(1), "middle")
    # Fallback
    return "middle"


def divine_assistance_combat(character: Character, monster: Monster) -> bool:
    wis = character.attributes.get("Wisdom", 10)
    roll = roll_damage("5d4") + (wis - 10)
    print(
        get_dialogue("combat", "divine_attempt", None, character)
        or f"You call for divine aid... Roll {roll}"
    )
    if roll >= 12:
        # Higher rolls favor stronger aid
        if roll >= 16:
            die = "4d6"
            name = "Fireball"
        else:
            die = "3d6"
            name = "Lightning Bolt"
        dmg = max(1, roll_damage(die))
        monster.hp -= dmg
        print(
            get_dialogue("combat", "divine_success", None, character)
            or f"The gods answer with {name} for {dmg} damage! Monster HP: {max(monster.hp, 0)}"
        )
        return True
    else:
        print(
            get_dialogue("combat", "divine_fail", None, character)
            or "Your plea goes unanswered."
        )
        return False


def apply_poison_dot(character: Character) -> None:
    dur = character.persistent_buffs.get("debuff_poison", 0)
    if dur > 0:
        dmg = max(1, roll_damage("1d4"))
        character.hp -= dmg
        character.persistent_buffs["debuff_poison"] = dur - 1
        print(
            get_dialogue("combat", "poison_dot", None, character)
            or f"Poison saps you for {dmg} damage. ({dur-1} turns remain)"
        )


def charm_monster(character: Character, monster: Monster) -> bool:
    cha = character.attributes.get("Charisma", 10)
    roll = roll_damage("5d4") + cha
    raw = get_dialogue("combat", "charm_attempt", None, character)
    if raw:
        try:
            print(raw.format(roll=roll, name=monster.name))
        except Exception:
            print(raw)
    else:
        print(f"You attempt to charm the {monster.name}... Roll {roll}")
    if roll > 30:
        msg = get_dialogue("combat", "charm_success", None, character)
        if msg:
            try:
                print(msg.format(name=monster.name))
            except Exception:
                print(msg)
        else:
            print(f"The {monster.name} is charmed and leaves peacefully.")
        return True
    else:
        msg = get_dialogue("combat", "charm_fail", None, character)
        print(msg or "Your charm attempt fails.")
        return False


def run_away(character: Character, monster: Monster) -> bool:
    dex = character.attributes.get("Dexterity", 10)
    # Use a simple Dexterity bonus (Dex/2 rounded up) for escape attempts so thresholds are reasonable
    dex_bonus = math.ceil(dex / 2)
    monster_dex = getattr(monster, "dexterity", 10)
    monster_bonus = math.ceil(monster_dex / 2)
    attack_die = roll_damage("5d4")
    roll = attack_die + dex_bonus
    threshold = 15 + monster_bonus
    raw = get_dialogue("combat", "run_attempt", None, character)
    if raw:
        try:
            print(
                raw.format(
                    roll=roll,
                    attack_die=attack_die,
                    dex_bonus=dex_bonus,
                    threshold=threshold,
                )
            )
        except Exception:
            print(raw)
    else:
        print(
            f"You attempt to run away... Roll {roll} ({attack_die} + Dex/2({dex_bonus}) = {roll}) (need >{threshold})"
        )
    if roll > threshold:
        print(
            get_dialogue("combat", "run_success", None, character)
            or "You successfully escape!"
        )
        return True
    else:
        print(
            get_dialogue("combat", "run_fail", None, character) or "You fail to escape!"
        )
        return False


def player_turn(
    character: Character, monster: Monster, buffs: dict, enemy_debuffs: dict
) -> bool:
    apply_poison_dot(character)
    if character.hp <= 0:
        return True

    print("\n" + (get_dialogue("combat", "your_turn", None, character) or "Your turn:"))
    print(get_dialogue("combat", "combat_menu", None, character))
    print(get_dialogue("system", "enter_number", None, character) or ">")
    choice = input("> ").strip()
    if choice == "2":
        used = use_potion(character, buffs)
        return monster.hp <= 0 or used
    if choice == "3":
        cast = cast_spell(character, monster, buffs, enemy_debuffs)
        return monster.hp <= 0 or cast
    if choice == "4":
        used = divine_assistance_combat(character, monster)
        return monster.hp <= 0 or used
    if choice == "5":
        charmed = charm_monster(character, monster)
        return "charmed" if charmed else False
    if choice == "6":
        escaped = run_away(character, monster)
        return "escaped" if escaped else False
    if choice == "7":
        examine_monster(character, monster)
        return False  # Consumes turn
    # Attack
    zone = choose_aim_zone()
    weapon = choose_weapon(character)
    enemy_ac = max(1, monster.armor_class - enemy_debuffs.get("ac_penalty", 0))
    attack_die = roll_damage("5d4")
    str_mod = character.attributes.get("Strength", 10)
    attack_roll = attack_die + str_mod
    # Monster selects a defend zone (secret) to try to block your strike
    monster_defend_zone = random.choice(["high", "middle", "low"])
    print(
        f"You aim {zone} and roll: {attack_die} + Strength({str_mod}) = {attack_roll} vs AC {enemy_ac}"
    )
    print(f"The {monster.name} braces to defend {monster_defend_zone}.")
    # Fumble on minimum roll (5 for 5d4): you injure yourself
    if attack_die == 5:
        self_dmg = max(1, roll_damage("1d4"))
        character.hp -= self_dmg
        msg = get_dialogue("combat", "natural_one_self", None, character)
        if msg:
            try:
                print(msg.format(dmg=self_dmg, hp=max(character.hp, 0)))
            except Exception:
                print(msg)
        else:
            print(
                f"Massive fail! You injure yourself for {self_dmg} HP. Your HP: {max(character.hp, 0)}"
            )
        return monster.hp <= 0
    # Natural 20 always crits (ignores block)
    if attack_die == 20:
        # compute damage as a crit regardless of defend zone
        dmg_die = weapon.damage_die if weapon else "1d2"
        # NEW DAMAGE FORMULA: weapon_damage + math.ceil(strength / 2)
        strength_bonus = math.ceil(character.attributes.get("Strength", 10) / 2)
        base_dmg = roll_damage(dmg_die) + strength_bonus + buffs.get("damage_bonus", 0)
        if weapon and getattr(weapon, "damaged", False):
            base_dmg = max(1, base_dmg // 2)
        dmg = max(1, base_dmg)
        crit = int(dmg * 1.5)
        monster.hp -= crit
        print(f"Critical hit! You deal {crit} damage. Monster HP: {max(monster.hp, 0)}")
        # Monster hurt reaction (player hit) - print prefixed with monster name
        hurt = get_npc_dialogue("monster", "hurt_reaction", None, monster)
        if hurt:
            try:
                text = hurt.format(name=monster.name)
            except Exception:
                text = hurt
            if monster.name not in text:
                text = f"{monster.name}: {text}"
            print(text)
        # On critical hits, higher chance to damage monster defenses
        try:
            mc = getattr(monster, "armor_class", 10)
            extra_chance = min(0.5, 0.005 * mc)
            if random.random() < extra_chance:
                enemy_debuffs["crippled"] = True
                print("The blow rends the creature's defenses — it is crippled!")
        except Exception:
            pass
        # Chance to damage player's weapon on successful hit (0.1% per monster AC)
        try:
            mc = getattr(monster, "armor_class", 10)
            chance = mc * 0.001
            if random.random() < chance and weapon:
                weapon.damaged = True
                print(f"Unlucky! Your {weapon.name} is damaged and now less effective.")
        except Exception:
            pass
        return monster.hp <= 0
    # Perfect defense blocks even a strong hit (non-crit)
    if monster_defend_zone == zone:
        print(f"Your attack is blocked by the {monster_defend_zone} guard!")
        # Even blocked (non-crit) attacks can damage equipment per new rules (chance based on monster AC)
        try:
            mc = getattr(monster, "armor_class", 10)
            chance = mc * 0.001
            if random.random() < chance and weapon:
                weapon.damaged = True
                print(f"Unlucky! Your {weapon.name} is damaged and now less effective.")
        except Exception:
            pass
        return monster.hp <= 0
    if attack_roll >= enemy_ac:
        dmg_die = weapon.damage_die if weapon else "1d2"
        # NEW DAMAGE FORMULA: weapon_damage + math.ceil(strength / 2)
        strength_bonus = math.ceil(character.attributes.get("Strength", 10) / 2)
        base_dmg = roll_damage(dmg_die) + strength_bonus + buffs.get("damage_bonus", 0)
        # Apply damaged weapon reduction (damaged weapons do half damage)
        if weapon and getattr(weapon, "damaged", False):
            base_dmg = max(1, base_dmg // 2)
        dmg = max(1, base_dmg)
        # Handle criticals vs normal hits
        if attack_die == 20:
            crit = int(dmg * 1.5)
            monster.hp -= crit
            print(
                f"Critical hit! You deal {crit} damage. Monster HP: {max(monster.hp, 0)}"
            )
            # Monster hurt reaction (prefixed with monster name/role)
            hurt = get_npc_dialogue("monster", "hurt_reaction", None, monster)
            if hurt:
                try:
                    text = hurt.format(name=monster.name)
                except Exception:
                    text = hurt
                if monster.name not in text:
                    text = f"{monster.name}: {text}"
                print(text)
            # On critical hits, higher chance to damage monster defenses
            try:
                mc = getattr(monster, "armor_class", 10)
                extra_chance = min(0.5, 0.005 * mc)
                if random.random() < extra_chance:
                    enemy_debuffs["crippled"] = True
                    print("The blow rends the creature's defenses — it is crippled!")
            except Exception:
                pass
        else:
            # Normal hit
            monster.hp -= dmg
            print(f"Hit! You deal {dmg} damage. Monster HP: {max(monster.hp, 0)}")
            # Monster hurt reaction (prefixed with monster name/role)
            hurt = get_npc_dialogue("monster", "hurt_reaction", None, monster)
            if hurt:
                print(hurt)
        # Chance to damage player's weapon on successful hit (0.1% per monster AC)
        try:
            mc = getattr(monster, "armor_class", 10)
            chance = mc * 0.001
            if random.random() < chance and weapon:
                weapon.damaged = True
                print(f"Unlucky! Your {weapon.name} is damaged and now less effective.")
        except Exception:
            pass
    else:
        miss = get_dialogue("system", "tips", None, character) or "You miss!"
        print(miss)
    if buffs.get("extra_attack_charges", 0) > 0 and monster.hp > 0 and choice == "1":
        buffs["extra_attack_charges"] -= 1
        print("Your speed grants you an extra strike!")
        return player_turn(character, monster, buffs, enemy_debuffs)
    return monster.hp <= 0


def monster_turn(
    character: Character, monster: Monster, buffs: dict, enemy_debuffs: dict
) -> bool:
    if enemy_debuffs.get("freeze_turns", 0) > 0:
        enemy_debuffs["freeze_turns"] -= 1
        print("The monster is frozen and cannot act!")
        return False
    if buffs.get("invisibility_charges", 0) > 0:
        buffs["invisibility_charges"] -= 1
        print("The monster swings wildly but hits nothing!")
        return False
    # Monster prepares an unseen strike: choose attack zone (hidden)
    monster_zone = random.choice(["high", "middle", "low"])
    # Player chooses where to defend
    print("Prepare your guard before the attack lands.")
    player_defend_zone = choose_defend_zone()
    print(f"You brace to defend {player_defend_zone}.")
    # Roll attack
    ac = compute_armor_class(character, buffs.get("ac_bonus", 0))
    attack_die = roll_damage("5d4")
    monster_strength = getattr(monster, "strength", 10)
    strength_bonus = monster_strength // 2
    attack_roll = attack_die + strength_bonus
    print(
        f"{monster.name} attacks {monster_zone}: roll {attack_die} + Strength/2({strength_bonus}) = {attack_roll} vs AC {ac}"
    )
    # Fumble on minimum roll (5 for 5d4): monster injures itself
    if attack_die == 5:
        self_dmg = max(
            1, roll_damage(monster.damage_die) - enemy_debuffs.get("damage_penalty", 0)
        )
        monster.hp -= self_dmg
        msg = get_dialogue("combat", "monster_natural_one", None, character)
        if msg:
            try:
                print(msg.format(name=monster.name, dmg=self_dmg))
            except Exception:
                print(msg)
        else:
            print(f"{monster.name} blunders and injures itself for {self_dmg} HP!")
        return character.hp <= 0
    # Natural 20: monster critical hit (ignores defend zone)
    if attack_die == 20:
        dmg = max(
            1, roll_damage(monster.damage_die) - enemy_debuffs.get("damage_penalty", 0)
        )
        crit = int(dmg * 1.5)
        character.hp -= crit
        print(f"Critical hit! You take {crit} damage. Your HP: {max(character.hp, 0)}")
        # Chance to damage player's armor on successful monster hit (0.1% per monster strength)
        try:
            ms = getattr(monster, "strength", getattr(monster, "base_strength", 10))
            chance = ms * 0.001
            if random.random() < chance and character.armor:
                character.armor.damaged = True
                print(
                    f"Ouch! Your {character.armor.name} is damaged and provides reduced protection."
                )
        except Exception:
            pass
        return character.hp <= 0
    # Perfect defense blocks regardless of roll (non-crit)
    if player_defend_zone == monster_zone:
        print(f"You successfully defend against the {monster_zone} attack!")
        # Blocked attacks still can damage armor per new rules
        try:
            ms = getattr(monster, "strength", getattr(monster, "base_strength", 10))
            chance = ms * 0.001
            if random.random() < chance and character.armor:
                character.armor.damaged = True
                print(
                    f"Ouch! Your {character.armor.name} is damaged and provides reduced protection."
                )
        except Exception:
            pass
        return character.hp <= 0
    # Otherwise resolve normally against AC
    if attack_roll >= ac:
        dmg = max(
            1, roll_damage(monster.damage_die) - enemy_debuffs.get("damage_penalty", 0)
        )
        character.hp -= dmg
        print(f"You are hit for {dmg} damage. Your HP: {max(character.hp, 0)}")
        # Chance to damage player's armor on successful monster hit (0.1% per monster strength)
        try:
            ms = getattr(monster, "strength", getattr(monster, "base_strength", 10))
            chance = ms * 0.001
            if random.random() < chance and character.armor:
                character.armor.damaged = True
                print(
                    f"Ouch! Your {character.armor.name} is damaged and provides reduced protection."
                )
        except Exception:
            pass
    else:
        print(f"{monster.name} misses!")
    return character.hp <= 0


def initiative_order(character: Character, monster: Monster) -> str:
    cdx = character.attributes.get("Dexterity", 10)
    mdx = getattr(monster, "dexterity", 10)
    c_roll = roll_damage("5d4") + cdx
    m_roll = roll_damage("5d4") + mdx
    print(
        f"Initiative - You: {c_roll} (roll + {cdx}) vs Monster: {m_roll} (roll + {mdx})"
    )
    return "player" if c_roll >= m_roll else "monster"


def combat_encounter(character: Character, monster: Monster) -> tuple[bool, str]:
    """
    Returns (combat_result, exit_reason)
    combat_result: True if player won, False if player lost
    exit_reason: 'victory', 'defeat', 'charmed', 'escaped', 'teleported'
    """
    # Monster entry taunt/appearance. Prefer a dialogue-driven taunt; if that
    # dialogue is more descriptive, make sure to also include the monster's name
    # so players see both description and the monster identity.
    monster_taunt = get_dialogue(
        "monster", "taunt_entry", None, monster
    ) or get_dialogue("monster", "taunt_entry", None, character)
    if monster_taunt:
        # If the taunt doesn't mention the monster name, append it for clarity.
        if "{name}" in monster_taunt:
            print(monster_taunt.format(name=monster.name))
        else:
            print(f"{monster_taunt}\nA {monster.name} appears!")
    else:
        print(f"A {monster.name} appears!")
    print("You can try to examine it with a Wisdom check (consumes your turn)")
    buffs = {}
    enemy_debuffs = {}
    turn = initiative_order(character, monster)
    while character.hp > 0 and monster.hp > 0:
        try:
            if turn == "player":
                result = player_turn(character, monster, buffs, enemy_debuffs)
                if result == "charmed":
                    return True, "charmed"
                elif result == "escaped":
                    return True, "escaped"
                elif result:
                    # Monster defeated
                    pass
                # Companion acts after player
                if (
                    character.companion
                    and character.companion.hp > 0
                    and monster.hp > 0
                ):
                    companion_turn(character, monster)
                turn = "monster"
            else:
                if monster_turn(character, monster, buffs, enemy_debuffs):
                    pass
                turn = "player"
        except TeleportToTown:
            raise
        if monster.hp <= 0 or character.hp <= 0:
            break

    if character.hp <= 0:
        return False, "defeat"
    elif monster.hp <= 0:
        return True, "victory"
    else:
        return False, "unknown"
