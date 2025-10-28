"""
CLI ENTRY REMOVED
-----------------
This project now uses a web-only engine served by web_app.py.
Importing this module is unsupported; run the web app instead.
"""

raise ImportError(
    "CLI (__main__) is removed. Use the web app (web_app.py) with GameEngine."
)

import os
import math

from .dice import roll_d20, roll_damage
from .entities import Character, Weapon, Armor
from .shop import open_shop
from .labyrinth import generate_room
from .combat import combat_encounter, TeleportToTown
from .save import save_game, load_game, clear_save
from .town import (
    healer,
    tavern_drink,
    eat_meal,
    gambling,
    praying,
    side_quests,
    train,
    rest,
    companion_menu,
    weaponsmith,
    remove_curses,
)
from .quests import quest_manager
from .data_loader import (
    load_monster_sounds,
    load_monsters,
    load_spells,
    load_magic_items,
    load_weapons,
    load_armors,
    load_potions,
    get_dialogue,
    get_npc_dialogue,
)
from .traps import random_room_trap, resolve_trap
from .magic_items import examine_item, equip_magic_item

ATTRS = [
    "Strength",
    "Dexterity",
    "Constitution",
    "Intelligence",
    "Wisdom",
    "Charisma",
    "Perception",
]


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    # Use plain input() with no prompt so web clients can show their own Continue UI
    try:
        # Emit a sentinel that the web UI and subprocess reader can detect and show a Continue button.
        # This helps when the game runs in a separate subprocess (socket mode) where patched_input
        # is not available to emit the sentinel.
        try:
            print("[[PAUSE]]")
            # Ensure it's flushed immediately so remote clients receive it
            import sys as _sys

            try:
                _sys.stdout.flush()
            except Exception:
                pass
        except Exception:
            # In minimal environments, just continue to input()
            pass
        input()
    except Exception:
        # In environments where stdin isn't available, just pass
        pass


def roll_4d6_drop_lowest() -> int:
    # Using 4d6 drop lowest
    rolls = [roll_d20() // (20 // 6) for _ in range(4)]  # approximate 1-6 from d20
    # Replace with exact d6 using damage roller
    rolls = [max(1, min(6, roll_damage("1d6"))) for _ in range(4)]
    rolls.sort(reverse=True)
    return sum(rolls[:3])


def assign_attributes() -> dict:
    print(
        get_dialogue("system", "attribute_roll_intro", None, None)
        or "Rolling your attributes (d20 for each stat)..."
    )

    attrs = {}
    # Always ensure Perception is present in the list
    remaining_attrs = [
        "Strength",
        "Dexterity",
        "Constitution",
        "Intelligence",
        "Wisdom",
        "Charisma",
        "Perception",
    ]

    for i in range(len(ATTRS)):
        roll = roll_d20()
        # attribute roll intro (supports formatting)
        intro = get_dialogue("system", "attribute_roll", None, None)
        if intro:
            try:
                print(intro.format(i=i + 1, total=len(ATTRS)))
            except Exception:
                print(f"\nRolling for attribute {i+1} of {len(ATTRS)}...")
        else:
            print(f"\nRolling for attribute {i+1} of {len(ATTRS)}...")

        # rolled message
        rolled = get_dialogue("system", "you_rolled", None, None)
        if rolled:
            try:
                print(rolled.format(roll=roll))
            except Exception:
                print(f"You rolled a {roll}!")
        else:
            print(f"You rolled a {roll}!")

        print(
            get_dialogue("system", "choose_attribute", None, None)
            or "Choose which attribute to assign this value to:"
        )
        for idx, attr in enumerate(remaining_attrs, start=1):
            print(f"{idx}) {attr}")

        # After listing all remaining attributes, prompt the player for their choice once
        print(get_dialogue("system", "enter_number", None, None) or "Enter the number:")
        choice = input("> ").strip()
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(remaining_attrs):
                selected_attr = remaining_attrs.pop(choice_idx)
                attrs[selected_attr] = roll
                print(f"Assigned {roll} to {selected_attr}!")
            else:
                # Default to first remaining attribute
                selected_attr = remaining_attrs.pop(0)
                attrs[selected_attr] = roll
                print(f"Invalid choice. Assigned {roll} to {selected_attr}!")
        except Exception:
            # Default to first remaining attribute
            selected_attr = remaining_attrs.pop(0)
            attrs[selected_attr] = roll
            print(f"Invalid input. Assigned {roll} to {selected_attr}!")

    return attrs


def compute_hp_and_gold(attrs: dict) -> tuple[int, int]:
    print(
        get_dialogue("system", "calc_hp_gold", None, None)
        or "\nCalculating your starting HP and Gold..."
    )
    # HP = 3 * CON + 3d6
    con = attrs.get("Constitution", 10)
    print(
        (
            get_dialogue("system", "your_constitution", None, None)
            or "Your Constitution is {con}..."
        ).format(con=con)
    )
    print(
        get_dialogue("system", "rolling_hp_bonus", None, None)
        or "Rolling 3d6 for HP bonus..."
    )
    hp_bonus = roll_damage("3d6")
    hp = 3 * con + hp_bonus
    print(
        (
            get_dialogue("system", "hp_result", None, None)
            or "Base HP: {base} + Bonus: {bonus} = {hp} HP!"
        ).format(base=2 * con, bonus=hp_bonus, hp=hp)
    )

    # Gold = 20d6 + bonus 5d6..10d6 for high CHA or low HP
    print(
        get_dialogue("system", "rolling_gold", None, None)
        or "Rolling 20d6 for starting gold..."
    )
    gold = roll_damage("20d6")
    cha = attrs.get("Charisma", 10)
    bonus = 0
    if cha >= 15:
        print(
            (
                get_dialogue("system", "cha_high_roll", None, None)
                or f"High Charisma ({cha})! Rolling 10d6 bonus gold..."
            ).format(cha=cha)
        )
        bonus = roll_damage("10d6")
    elif cha >= 12:
        print(
            (
                get_dialogue("system", "cha_good_roll", None, None)
                or f"Good Charisma ({cha})! Rolling 7d6 bonus gold..."
            ).format(cha=cha)
        )
        bonus = roll_damage("7d6")
    elif hp < 20:
        print(
            (
                get_dialogue("system", "low_hp_roll", None, None)
                or f"Low HP ({hp})! Rolling 10d6 bonus gold..."
            ).format(hp=hp)
        )
        bonus = roll_damage("10d6")
    else:
        print(
            get_dialogue("system", "standard_gold_roll", None, None)
            or "Rolling 5d6 bonus gold..."
        )
        bonus = roll_damage("5d6")
    gold += bonus
    print(
        (
            get_dialogue("system", "gold_result", None, None)
            or "Base Gold: {base_minus_bonus} + Bonus: {bonus} = {gold} Gold!"
        ).format(base_minus_bonus=gold - bonus, bonus=bonus, gold=gold)
    )
    return hp, gold


def main_menu() -> None:
    while True:
        clear_screen()
        print(
            get_dialogue("system", "main_menu_header", None, None)
            or "=== Labyrinth Adventure (CLI) ==="
        )
        print(get_dialogue("system", "main_menu_new", None, None) or "1) New Game")
        print(get_dialogue("system", "main_menu_load", None, None) or "2) Load Game")
        print(get_dialogue("system", "main_menu_quit", None, None) or "3) Quit")
        print(get_dialogue("system", "enter_number", None, None) or ">")
        choice = input("> ").strip()
        if choice == "1":
            # Require explicit confirmation to start a new game to avoid accidental
            # immediate character creation (for example after a death that cleared save)
            print(
                get_dialogue("system", "confirm_new_game", None, None)
                or "Start a new game? (y/n)"
            )
            conf = input("> ").strip().lower()
            if conf == "y":
                game_loop(new_game())
        elif choice == "2":
            character = load_game()
            if character:
                game_loop(character)
            else:
                print(
                    get_dialogue("system", "no_saved_game", None, None)
                    or "No saved game found."
                )
                pause()
        elif choice == "3":
            return
        else:
            print(
                get_dialogue("system", "invalid_choice", None, None)
                or "Invalid choice."
            )
            pause()


def new_game() -> Character:
    clear_screen()
    # Single story plot to explain the world and labyrinth
    print(
        "In a world where reality itself bears ancient scars, mysterious labyrinths manifest without warning. These maze-like structures warp space and time, appearing at civilization's edge. Within their shifting corridors, a corrupted Dragon - once a guardian of reality - now feeds the maze with its rage. You have three days before this labyrinth destabilizes, threatening to tear reality apart."
    )
    print(
        "\nThe town of Darsen stands as humanity's last outpost near this latest breach. No Explorer has arrived to face this challenge, leaving you as their only hope. Your journey to become an Explorer - one of the legendary few who can navigate these reality-warping mazes - begins here."
    )
    pause()  # Let them read the story
    clear_screen()
    print("What is your name, aspiring Explorer?")
    # Use prompted input so web clients show a free-text input box for the name
    name = input("> ").strip() or "Adventurer"

    # Create character without class or starting equipment
    character = Character(name=name, clazz="Adventurer", max_hp=1, gold=0)

    # Attributes
    attrs = assign_attributes()
    character.attributes = attrs
    # HP and Gold per rules
    hp, gold = compute_hp_and_gold(attrs)
    character.max_hp = hp
    character.hp = character.max_hp
    character.gold = gold

    # Pause here so web UI shows a Continue button before the remaining creation text
    pause()

    print(
        get_dialogue("system", "creation_complete", None, character)
        or "\nCharacter creation complete!"
    )
    name_line = get_dialogue("system", "creation_name_line", None, character)
    print(
        name_line.format(name=character.name)
        if name_line
        else f"Name: {character.name}"
    )
    hp_line = get_dialogue("system", "creation_hp_line", None, character)
    print(hp_line.format(hp=character.max_hp) if hp_line else f"HP: {character.max_hp}")
    gold_line = get_dialogue("system", "creation_gold_line", None, character)
    print(
        gold_line.format(gold=character.gold)
        if gold_line
        else f"Gold: {character.gold}"
    )
    print(
        get_dialogue("system", "starting_note", None, character)
        or "You start with no weapons or armor - visit the shop to equip yourself!. Best of luck adventurer"
    )
    pause()
    return character


def town_menu(character: Character) -> None:
    while True:
        clear_screen()
        print(f"=== Town of Darsen ===\n{character.summary()}\n")
        # Reordered per UI request: 1) Venture, 2) Shop, 3) Inventory, rest follow
        # Simplified menu with direct options
        print(
            """1) Venture into the Labyrinth
2) Visit Shop
3) Inventory
4) Rest at the Inn (10g)
5) Visit Healer (20g)
6) Tavern (5g)
7) Eat (10g)
8) Gamble
9) Temple
10) Level Up
11) Quests
12) Train (50g)
13) Sleep 
14) Companion
15) Repair (30g)
16) Remove Curses (10g)
17) Save
18) Quit"""
        )
        print("> ")
        choice = input("> ").strip()
        if choice == "1":
            # Gate guard flavor will be shown inside the dungeon run (immediately after
            # the labyrinth header and character summary) so the guard's name prefixes
            # the dialogue consistently using get_npc_dialogue().
            character.rest_attempted = False
            character.prayed = False
            dungeon_run(character)
            # Ensure the flag is cleared after returning from the dungeon
            character.rest_attempted = False
            character.prayed = False
            if character.hp <= 0:
                print(
                    get_dialogue("system", "death", None, character)
                    or "You have died! Game Over!"
                )
                # Clear persistent save to prevent save-scumming
                try:
                    clear_save()
                except Exception:
                    pass
                pause()
                return
        elif choice == "2":
            open_shop(character)
        elif choice == "3":
            inventory_menu(character)
        elif choice == "4":
            rest(character)
        elif choice == "5":
            healer(character)
        elif choice == "6":
            tavern_drink(character)
        elif choice == "7":
            eat_meal(character)
        elif choice == "8":
            gambling(character)
        elif choice == "9":
            praying(character)
        elif choice == "10":
            # Auto-level if enough XP
            if character.xp >= (character.level + 1) * 100:
                msgs = character.gain_level()
                for msg in msgs:
                    print(msg)
                pause()
            else:
                print(
                    get_dialogue("system", "not_enough_xp", None, character)
                    or f"Not enough XP! Need {(character.level + 1) * 100 - character.xp} more XP to level up."
                )
                pause()
        elif choice == "11":
            side_quests(character)
        elif choice == "12":
            train(character)
        elif choice == "13":
            rest(character)
        elif choice == "14":
            companion_menu(character)
        elif choice == "15":
            weaponsmith(character)
        elif choice == "16":
            remove_curses(character)
        elif choice == "17":
            save_game(character)
            print(
                get_dialogue("system", "game_saved", None, character)
                or "Game saved successfully!"
            )
            pause()
        elif choice == "18":
            if not character.rest_attempted:
                print(
                    get_dialogue("system", "quit_warning", None, character)
                    or "Warning: You haven't rested! Your progress may not be saved."
                )
                print(
                    get_dialogue("system", "quit_confirm", None, character)
                    or "Are you sure you want to quit? (y/n)"
                )
                if input("> ").strip().lower() != "y":
                    continue
            return

        else:
            print(
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid choice."
            )
            pause()


def dungeon_run(character: Character) -> None:
    depth = 1
    room_history = []  # Track room history for navigation
    room = None

    while True:
        clear_screen()
        # Labyrinth header (dialogue-driven if available)
        d_hdr = get_dialogue("system", "labyrinth_header", None, character)
        print(
            f"{d_hdr.format(depth=depth)}\n{character.summary()}\n"
            if d_hdr
            else f"=== Labyrinth Depth {depth} ===\n{character.summary()}\n"
        )
        # Show a single initial NPC/dialogue line (for example, the gate guard greeting)
        # Print this BEFORE traps and room generation so flavor appears in the expected order.
        # Only show the gate guard greeting on the very first entry into the labyrinth
        if depth == 1 and room is None:
            greeting = get_npc_dialogue("town", "gate_guard", None, character)
            if greeting:
                print(greeting)
        # Generate room and chance for a room trap only when entering a new room
        if room is None:
            # Chance for a room trap
            trap = random_room_trap()
            if trap:
                resolve_trap(character, trap)
                if character.hp <= 0:
                    print(
                        get_dialogue("system", "succumb_trap", None, character)
                        or "You succumb to the trap..."
                    )
                    print(
                        get_dialogue("system", "death", None, character)
                        or "You have died! Game Over!"
                    )
                    # Clear persistent save to prevent save-scumming
                    try:
                        clear_save()
                    except Exception:
                        pass
                    pause()
                    return
            room = generate_room(depth, character)
            # Use dialogue-driven room entry if available
            print(room.description)
            # If the room contains a monster and the monster has a description in data, print
            # that description BEFORE the monster's name/appearance line so ordering is
            # room description -> monster description -> monster name.
            if room.monster:
                from .data_loader import load_monsters

                monster_data = next(
                    (m for m in load_monsters() if m.get("name") == room.monster.name),
                    None,
                )
                if monster_data:
                    desc = monster_data.get("description")
                    if desc:
                        print(desc)

        # Display chest if present
        if room.has_chest:
            chest_msg = (
                get_dialogue("chest", "before_opening", None, character)
                or "You notice a treasure chest in the room!"
            )
            print(chest_msg)

        if room.monster:
            appear = get_dialogue("system", "monster_appears", None, character)
            print(
                appear.format(name=room.monster.name)
                if appear
                else get_dialogue(
                    "system", "combat_monster_appears", None, None
                ).format(name=room.monster.name)
            )
            try:
                won, exit_reason = combat_encounter(character, room.monster)
            except TeleportToTown:
                print(
                    get_dialogue("combat", "teleport_to_town", None, character)
                    or "You return to town via teleport."
                )
                pause()
                return

            if not won:
                print(
                    get_dialogue("system", "you_were_defeated", None, character)
                    or "You were defeated..."
                )
                if character.hp <= 0:
                    print(
                        get_dialogue("system", "death", None, character)
                        or "You have died! Game Over!"
                    )
                    # Clear persistent save to prevent save-scumming
                    try:
                        clear_save()
                    except Exception:
                        pass
                    pause()
                    return
                pause()
                return
            elif exit_reason == "victory":
                # Award XP and gold based on monster data
                monster_data = next(
                    (m for m in load_monsters() if m.get("name") == room.monster.name),
                    None,
                )
                if monster_data:
                    xp_reward = int(monster_data.get("xp", 10))
                    msgs = character.gain_xp(xp_reward)
                    print(
                        get_dialogue(
                            "system", "combat_monster_defeated", None, character
                        ).format(name=room.monster.name, xp=xp_reward)
                        or f"You defeated the {room.monster.name} and gain {xp_reward} XP!"
                    )
                    for m in msgs:
                        print(m)
                else:
                    msgs = character.gain_xp(10)
                    print(
                        get_dialogue(
                            "system", "combat_monster_defeated", None, character
                        ).format(name=room.monster.name, xp=10)
                        or f"You defeated the {room.monster.name} and gain 10 XP!"
                    )
                    for m in msgs:
                        print(m)

                character.gold += room.gold_reward
                print(
                    get_dialogue("system", "you_loot_gold", None, character).format(
                        gold=room.gold_reward
                    )
                    if get_dialogue("system", "you_loot_gold", None, character)
                    else f"You loot {room.gold_reward} gold!"
                )

                # Rare chance for potion or spell drop
                import random

                if random.random() < 0.1:  # 10% chance
                    if random.random() < 0.5:
                        # Potion drop
                        character.potions += 1
                        print(
                            get_dialogue(
                                "system", "find_healing_potion", None, character
                            )
                            or "You find a healing potion!"
                        )
                    else:
                        # Spell drop (random spell from data)
                        spells = load_spells()
                        if spells:
                            spell = random.choice(spells)
                            spell_name = spell.get("name", "Unknown Spell")
                            character.spells[spell_name] = (
                                character.spells.get(spell_name, 0) + 1
                            )
                            print(
                                get_dialogue(
                                    "system", "find_scroll_of_spell", None, character
                                ).format(spell=spell_name)
                                if get_dialogue(
                                    "system", "find_scroll_of_spell", None, character
                                )
                                else f"You find a scroll of {spell_name}!"
                            )

                # Clear the monster from the room so it does not respawn or cause another combat
                try:
                    room.monster = None
                except Exception:
                    pass
                # Update side quests (if any) based on this kill
                try:
                    changed = quest_manager.check_kill(character, room.monster)
                    for q in changed:
                        print(
                            f"Side Quest Updated: {q.desc} - Completed! Reward: {q.reward}g"
                        )
                except Exception:
                    # Non-fatal if quests fail
                    pass
            elif exit_reason == "charmed":
                print(
                    get_dialogue("system", "monster_left_peacefully", None, character)
                    or "The monster has left peacefully. You remain in this room."
                )
                # Ensure the monster is removed from the room after being charmed
                try:
                    room.monster = None
                except Exception:
                    pass
            elif exit_reason == "escaped":
                print(
                    get_dialogue("system", "escaped_previous_room", None, character)
                    or "You successfully escape to the previous room!"
                )
                if room_history:
                    depth = room_history.pop()
                    # ensure we regenerate the room at the restored depth
                    room = None
                    continue
                else:
                    print(
                        get_dialogue("system", "escape_back_to_town", None, character)
                        or "You escape back to town!"
                    )
                    return
        else:
            quiet_msg = (
                get_dialogue("labyrinth", "examine_room", None, character)
                or "The room is quiet..."
            )
            print(quiet_msg)

        # Room navigation options
        nav = get_dialogue("system", "labyrinth_navigation_options", None, character)
        if nav:
            print(nav)
        else:
            print("\n1) Go deeper")
            if depth > 1 or room_history:
                print("2) Go back")
            else:
                print("2) Return to town")
            print("3) Ask for divine assistance")
            print("4) Listen at the door")
            print("5) Open a chest")
            print("6) Examine magic item")
        choice = input("> ").strip()

        if choice == "1":
            room_history.append(depth)
            depth += 1
            # moving deeper -> generate a new room next iteration
            room = None
        elif choice == "2":
            if depth > 1 or room_history:
                if room_history:
                    depth = room_history.pop()
                else:
                    depth -= 1
                # moving back -> regenerate the appropriate room next iteration
                room = None
            else:
                return
        elif choice == "3":
            roll = roll_d20() + (
                2
                if character.attributes.get("Wisdom", 10) >= 15
                else (1 if character.attributes.get("Wisdom", 10) >= 12 else 0)
            )
            div = get_dialogue("combat", "divine_attempt", None, character)
            print(
                div.format(roll=roll)
                if div
                else f"You pray for guidance... Roll {roll}"
            )
            if roll >= 12:
                next_room = generate_room(depth + 1)
                if next_room.monster:
                    vision = get_dialogue("system", "vision_monster", None, character)
                    print(
                        vision.format(name=next_room.monster.name)
                        if vision
                        else f"A vision shows a {next_room.monster.name} ahead."
                    )
                else:
                    print(
                        get_dialogue("system", "vision_empty", None, character)
                        or "A vision shows an empty corridor ahead."
                    )
            else:
                print(
                    get_dialogue("system", "no_vision", None, character)
                    or "No vision comes."
                )
            pause()
        elif choice == "4":
            # Perception adds a direct modifier (can be negative). Use (Perception - 10).
            per = character.attributes.get("Perception", 10)
            bonus = per - 10
            base_roll = roll_d20()
            final_roll = base_roll + bonus
            # Show roll details if dialogue not provided
            listen = get_dialogue("system", "listen_roll", None, character)
            print(
                listen.format(roll=final_roll)
                if listen
                else f"You listen carefully... Roll {base_roll} + Bonus {bonus} = {final_roll}"
            )
            # Success threshold is based on final_roll
            if final_roll >= 12:
                sounds = load_monster_sounds()
                mapping = {
                    s.get("name", "").lower(): s.get("sound", "Unknown") for s in sounds
                }
                next_room = generate_room(depth + 1)
                if next_room.monster:
                    name = next_room.monster.name.lower()
                    hint = mapping.get(name, "Unknown")
                    print(
                        get_dialogue("system", "you_hear", None, character).format(
                            hint=hint
                        )
                        if get_dialogue("system", "you_hear", None, character)
                        else f"You hear: {hint}."
                    )
                else:
                    print(
                        get_dialogue("system", "sounds_quiet", None, character)
                        or "It sounds quiet ahead."
                    )
            else:
                print(
                    get_dialogue("system", "hear_nothing", None, character)
                    or "You hear nothing useful."
                )
            pause()
        elif choice == "5":
            if not room.has_chest:
                print(
                    get_dialogue("system", "no_chest", None, character)
                    or "There is no chest in this room."
                )
                pause()
            else:
                # Chest always has gold
                character.gold += room.chest_gold
                print(
                    get_dialogue("system", "open_chest_gold", None, character).format(
                        gold=room.chest_gold
                    )
                    if get_dialogue("system", "open_chest_gold", None, character)
                    else f"You open the chest and find {room.chest_gold} gold!"
                )

                # Check for magic item
                if room.chest_magic_item:
                    # Auto-equip magic item (cannot be removed)
                    from .magic_items import auto_equip_magic_item

                    item_name = room.chest_magic_item
                    print(
                        get_dialogue(
                            "system", "find_magic_item", None, character
                        ).format(item=item_name)
                        if get_dialogue("system", "find_magic_item", None, character)
                        else f"You also find a {item_name}!"
                    )
                    # auto_equip_magic_item(character, item_name)

                # Mark chest as opened and remain in the same room (no automatic regeneration)
                room.has_chest = False
        elif choice == "6":
            # Examine magic items in inventory
            if not character.magic_items:
                print(
                    get_dialogue("system", "no_magic_items", None, character)
                    or "You have no magic items to examine."
                )
            else:
                print(
                    get_dialogue("system", "magic_items_list", None, character)
                    or "Magic items in your possession:"
                )
                for i, item in enumerate(character.magic_items, 1):
                    print(f"{i}) {item.name}")
                choice = input("Examine which item? (number) > ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(character.magic_items):
                        print(examine_item(character.magic_items[idx]))
            pause()
        else:
            print(
                get_dialogue("system", "hesitate_return", None, character)
                or "You hesitate and decide to return to town."
            )
            return


def inventory_menu(character: Character) -> None:
    while True:
        # Header
        print(
            get_dialogue("system", "inventory_header", None, character)
            or "\n=== Inventory ==="
        )
        current_weapon = "Unarmed"
        if 0 <= character.equipped_weapon_index < len(character.weapons):
            cw = character.weapons[character.equipped_weapon_index]
            current_weapon = cw.name + (
                " (damaged)" if getattr(cw, "damaged", False) else ""
            )
        # Equipped weapon display (use dialogue if available)
        weapon_line = get_dialogue(
            "system", "inventory_equipped_weapon", None, character
        )
        if weapon_line:
            print(weapon_line.format(weapon=current_weapon))
        else:
            print(f"Equipped weapon: {current_weapon}")
        armor_display = "None"
        if character.armor:
            armor_display = character.armor.name + (
                " (damaged)" if getattr(character.armor, "damaged", False) else ""
            )
        # Equipped armor line
        armor_line = get_dialogue("system", "inventory_equipped_armor", None, character)
        if armor_line:
            print(
                armor_line.format(
                    armor=armor_display,
                    ac=(character.armor.armor_class if character.armor else 10),
                )
            )
        else:
            print(
                f"Equipped armor: {armor_display} (AC {character.armor.armor_class if character.armor else 10})"
            )

        # Show full lists of all weapons and armor owned for quick reference
        print("\nAll weapons:")
        if not character.weapons:
            print("- None")
        else:
            for w in character.weapons:
                label = w.name + (" (damaged)" if getattr(w, "damaged", False) else "")
                print(f"- {label} ({getattr(w, 'damage_die', '1d4')})")

        print("\nAll armor:")
        # Include currently equipped armor first (if any), then owned armors
        if not character.armor and not character.armors_owned:
            print("- None")
        else:
            if character.armor:
                label = character.armor.name + (
                    " (damaged)" if getattr(character.armor, "damaged", False) else ""
                )
                print(f"- {label} (equipped) (AC {character.armor.armor_class})")
            for a in character.armors_owned:
                # avoid repeating the equipped armor
                if character.armor and a.name == character.armor.name:
                    continue
                label = a.name + (" (damaged)" if getattr(a, "damaged", False) else "")
                print(f"- {label} (AC {a.armor_class})")
        # Options block
        opts = get_dialogue("system", "inventory_options", None, character)
        if opts:
            print(opts)
        else:
            print("\n1) Equip weapon")
            print("2) Equip armor")
            print("3) View potions")
            print("4) Unequip weapon")
            print("5) Unequip armor")
            print("6) Back")
        choice = input("> ").strip()
        if choice == "1":
            if not character.weapons:
                print("You have no weapons.")
                continue
            for i, w in enumerate(character.weapons, 1):
                label = w.name + (" (damaged)" if getattr(w, "damaged", False) else "")
                print(f"{i}) {label} ({w.damage_die})")
            # Add Back option
            back_idx = len(character.weapons) + 1
            print(f"{back_idx}) Back")
            pick = input("Choose weapon > ").strip()
            if pick == str(back_idx):
                continue
            if pick.isdigit():
                idx = int(pick) - 1
                if 0 <= idx < len(character.weapons):
                    character.equipped_weapon_index = idx
                    print(f"Equipped {character.weapons[idx].name}.")
        elif choice == "2":
            if not character.armors_owned and not character.armor:
                print("You have no armor.")
                continue
            options = []
            if character.armor:
                options.append(character.armor)
            options.extend(
                a
                for a in character.armors_owned
                if (not character.armor or a.name != character.armor.name)
            )
            for i, a in enumerate(options, 1):
                label = a.name + (" (damaged)" if getattr(a, "damaged", False) else "")
                print(f"{i}) {label} (AC {a.armor_class})")
            # Add Back option
            back_idx = len(options) + 1
            print(f"{back_idx}) Back")
            pick = input("Choose armor > ").strip()
            if pick == str(back_idx):
                continue
            if pick.isdigit():
                idx = int(pick) - 1
                if 0 <= idx < len(options):
                    character.armor = options[idx]
                    print(f"Equipped {character.armor.name}.")
        elif choice == "3":
            if not character.potion_uses and character.potions <= 0:
                print("You have no potions.")
            else:
                print("Potions:")
                if character.potions > 0:
                    print(f"Healing (legacy): {character.potions}")
                for name, uses in character.potion_uses.items():
                    print(f"{name}: {uses} uses")
        elif choice == "4":
            # Unequip weapon
            if 0 <= character.equipped_weapon_index < len(character.weapons):
                print(
                    f"Unequipped {character.weapons[character.equipped_weapon_index].name}."
                )
                character.equipped_weapon_index = -1
            else:
                print("No weapon is currently equipped.")
            continue
        elif choice == "5":
            # Unequip armor
            if character.armor:
                print(f"Unequipped {character.armor.name}.")
                character.armor = None
            else:
                print("No armor is currently equipped.")
            continue
        elif choice == "6":
            return
        else:
            print("Invalid choice.")


def game_loop(character: Character) -> None:
    town_menu(character)


if __name__ == "__main__":
    main_menu()
