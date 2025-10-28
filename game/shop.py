from typing import Callable, Optional

from .entities import Character, Weapon, Armor
from .data_loader import (
    load_weapons,
    load_armors,
    load_potions,
    load_spells,
    get_dialogue,
    get_npc_dialogue,
)


# Minimal event emission helpers (mirrors helpers in town.py)
def _emit(
    emitter: Optional[Callable[[dict], None]], event_type: str, **payload
) -> None:
    if emitter:
        evt = {"type": event_type}
        evt.update(payload)
        try:
            emitter(evt)
        except Exception:
            pass


def _say(emitter: Optional[Callable[[dict], None]], text: str) -> None:
    _emit(emitter, "dialogue", text=text)


def open_shop(
    character: Character,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    weapons_data = [
        w
        for w in load_weapons()
        if int(w.get("price", 0)) > 0 and w.get("availability", "shop") != "labyrinth"
    ]
    armors_data = [
        a
        for a in load_armors()
        if int(a.get("price", 0)) > 0 and a.get("availability", "shop") != "labyrinth"
    ]
    potions_data = [
        p for p in load_potions() if int(p.get("cost", p.get("price", 0))) > 0
    ]
    spells_data = [s for s in load_spells() if int(s.get("cost", 0)) > 0]

    while True:
        # Show who is interacting and the player's current gold prominently
        line = f"{character.name} enters the shop."
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        # Shop header and buy prompt come from the shop NPC; prefix with name
        header = get_npc_dialogue("shop", "shop_header", None, character)
        if emitter:
            _say(emitter, header or "\n=== Shop ===")
        else:
            print(header or "\n=== Shop ===")
        # Always show a neutral gold line so the player can see their gold amount.
        gold_line = f"Gold: {character.gold}g"
        if emitter:
            _say(emitter, gold_line)
        else:
            print(gold_line)
        # Optionally show the NPC buy/sell blurb as flavor (do not replace the gold line)
        buy_line = get_npc_dialogue("shop", "buy", None, character)
        if buy_line:
            if emitter:
                _say(emitter, buy_line)
            else:
                print(buy_line)
        msg = (
            get_dialogue("shop", "choose_category", None, character)
            or "\nChoose a category:"
        )
        for line in [
            msg,
            get_dialogue("shop", "cat_weapons", None, character) or "1) Weapons",
            get_dialogue("shop", "cat_armor", None, character) or "2) Armor",
            get_dialogue("shop", "cat_potions", None, character) or "3) Potions",
            get_dialogue("shop", "cat_spells", None, character) or "4) Spells",
            get_dialogue("shop", "cat_sell", None, character) or "5) Sell items",
            get_dialogue("shop", "cat_leave", None, character) or "6) Leave Shop",
            get_dialogue("system", "enter", None, character) or ">",
        ]:
            if emitter:
                _say(emitter, line)
            else:
                print(line)
        choice = (chooser("> ") if chooser else input("> ")).strip()

        if choice == "1":
            browse_weapons(character, weapons_data, emitter=emitter, chooser=chooser)
        elif choice == "2":
            browse_armor(character, armors_data, emitter=emitter, chooser=chooser)
        elif choice == "3":
            browse_potions(character, potions_data, emitter=emitter, chooser=chooser)
        elif choice == "4":
            browse_spells(character, spells_data, emitter=emitter, chooser=chooser)
        elif choice == "5":
            sell_items(
                character,
                weapons_data,
                armors_data,
                potions_data,
                emitter=emitter,
                chooser=chooser,
            )
        elif choice == "6":
            return
        else:
            msg = (
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid choice."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)


def browse_weapons(
    character: Character,
    weapons_data: list,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    if not weapons_data:
        print(
            get_dialogue("shop", "no_weapons", None, character)
            or get_dialogue("shop", "no_gold", None, character)
            or "No weapons available."
        )
        return

    while True:
        line = f"{character.name} looks over the weapons for sale."
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        msg = (
            get_npc_dialogue("shop", "weapons_header", None, character)
            or "\n=== Weapons ==="
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        buy_line = get_npc_dialogue("shop", "buy", None, character)
        gold_line = f"Gold: {character.gold}g"
        if emitter:
            _say(emitter, gold_line)
        else:
            print(gold_line)
        if buy_line:
            if emitter:
                _say(emitter, buy_line)
            else:
                print(buy_line)
        line = (
            get_dialogue("shop", "back_main", None, character) or "1) Back to main shop"
        )
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        menu_index = 2
        weapon_options = []

        for w in weapons_data:
            msg = get_dialogue("shop", "weapon_entry", None, character)
            line = (
                msg.format(
                    idx=menu_index,
                    name=w.get("name"),
                    damage=w.get("damage_die", "1d4"),
                    price=w.get("price", 40),
                )
                if msg
                else f"{menu_index}) {w.get('name')} ({w.get('damage_die','1d4')} damage) ({w.get('price',40)}g)"
            )
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            weapon_options.append((menu_index, w))
            menu_index += 1

        line = ">"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        choice = (chooser("> ") if chooser else input("> ")).strip()
        if choice == "1":
            return
        elif choice.isdigit():
            idx = int(choice)
            for menu_idx, w in weapon_options:
                if idx == menu_idx:
                    price = int(w.get("price", 40))
                    if character.gold >= price:
                        character.gold -= price
                        character.weapons.append(
                            Weapon(
                                name=w.get("name", "Weapon"),
                                damage_die=w.get("damage_die", "1d4"),
                            )
                        )
                        msg = (
                            get_dialogue("shop", "buy", None, character)
                            or f"Purchased {w.get('name','Weapon')}. Use Inventory to equip it."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                        _emit(emitter, "state", gold=character.gold)
                    else:
                        msg = (
                            get_dialogue("shop", "no_gold", None, character)
                            or "Not enough gold."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                    break
        else:
            print(
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid choice."
            )


def browse_armor(
    character: Character,
    armors_data: list,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    if not armors_data:
        print(
            get_dialogue("shop", "no_armors", None, character)
            or get_dialogue("shop", "no_gold", None, character)
            or "No armor available."
        )
        return

    while True:
        line = f"{character.name} examines the armors on the racks."
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        msg = (
            get_npc_dialogue("shop", "armor_header", None, character)
            or "\n=== Armor ==="
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        buy_line = get_npc_dialogue("shop", "buy", None, character)
        gold_line = f"Gold: {character.gold}g"
        if emitter:
            _say(emitter, gold_line)
        else:
            print(gold_line)
        if buy_line:
            if emitter:
                _say(emitter, buy_line)
            else:
                print(buy_line)
        line = "1) Back to main shop"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        menu_index = 2
        armor_options = []

        for a in armors_data:
            msg = get_dialogue("shop", "armor_entry", None, character)
            line = (
                msg.format(
                    idx=menu_index,
                    name=a.get("name"),
                    ac=a.get("armor_class", 12),
                    price=a.get("price", 60),
                )
                if msg
                else f"{menu_index}) {a.get('name')} (AC {a.get('armor_class',12)}) ({a.get('price',60)}g)"
            )
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            armor_options.append((menu_index, a))
            menu_index += 1

        line = ">"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        choice = (chooser("> ") if chooser else input("> ")).strip()
        if choice == "1":
            return
        elif choice.isdigit():
            idx = int(choice)
            for menu_idx, a in armor_options:
                if idx == menu_idx:
                    price = int(a.get("price", 60))
                    if character.gold >= price:
                        character.gold -= price
                        new_armor = Armor(
                            name=a.get("name", "Armor"),
                            armor_class=int(a.get("armor_class", 12)),
                        )
                        character.armors_owned.append(new_armor)
                        character.armor = new_armor  # auto-equip latest
                        msg = (
                            get_dialogue("shop", "buy", None, character)
                            or f"Purchased and equipped {new_armor.name}."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                        _emit(emitter, "state", gold=character.gold)
                    else:
                        msg = (
                            get_dialogue("shop", "no_gold", None, character)
                            or "Not enough gold."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                    break
        else:
            print(
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid choice."
            )


def browse_potions(
    character: Character,
    potions_data: list,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    if not potions_data:
        print(
            get_dialogue("shop", "no_potions", None, character)
            or get_dialogue("shop", "no_gold", None, character)
            or "No potions available."
        )
        return

    while True:
        line = f"{character.name} browses the potions."
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        msg = (
            get_npc_dialogue("shop", "potions_header", None, character)
            or "\n=== Potions ==="
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        buy_line = get_npc_dialogue("shop", "buy", None, character)
        if buy_line:
            if emitter:
                _say(emitter, buy_line)
            else:
                print(buy_line)
        else:
            line = f"Gold: {character.gold}g"
            if emitter:
                _say(emitter, line)
            else:
                print(line)
        line = "1) Back to main shop"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        menu_index = 2
        potion_options = []

        for p in potions_data:
            price = int(p.get("cost", p.get("price", 0)))
            uses = int(p.get("uses", 1))
            msg = get_dialogue("shop", "potion_entry", None, character)
            line = (
                msg.format(idx=menu_index, name=p.get("name"), uses=uses, price=price)
                if msg
                else f"{menu_index}) {p.get('name')} ({uses} uses) ({price}g)"
            )
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            potion_options.append((menu_index, p))
            menu_index += 1

        line = ">"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        choice = (chooser("> ") if chooser else input("> ")).strip()
        if choice == "1":
            return
        elif choice.isdigit():
            idx = int(choice)
            for menu_idx, p in potion_options:
                if idx == menu_idx:
                    price = int(p.get("cost", p.get("price", 0)))
                    uses = int(p.get("uses", 1))
                    if character.gold >= price:
                        character.gold -= price
                        name = p.get("name", "Potion")
                        character.potion_uses[name] = (
                            character.potion_uses.get(name, 0) + uses
                        )
                        if name.lower() == "healing":
                            # Also increment legacy healing count for quick-consume compatibility
                            character.potions += 1
                        msg = (
                            get_dialogue("shop", "buy", None, character)
                            or f"Purchased {name} (+{uses} uses)."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                        _emit(emitter, "state", gold=character.gold)
                    else:
                        msg = (
                            get_dialogue("shop", "no_gold", None, character)
                            or "Not enough gold."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                    break
        else:
            print(
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid choice."
            )


def browse_spells(
    character: Character,
    spells_data: list,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    if not spells_data:
        print(
            get_dialogue("shop", "no_spells", None, character)
            or get_dialogue("shop", "no_gold", None, character)
            or "No spells available."
        )
        return

    while True:
        line = f"{character.name} inspects the spell scrolls on the shelf."
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        msg = (
            get_npc_dialogue("shop", "spells_header", None, character)
            or "\n=== Spells ==="
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        # Always show neutral gold and optionally an NPC blurb
        buy_line = get_npc_dialogue("shop", "buy", None, character)
        gold_line = f"Gold: {character.gold}g"
        if emitter:
            _say(emitter, gold_line)
        else:
            print(gold_line)
        if buy_line:
            if emitter:
                _say(emitter, buy_line)
            else:
                print(buy_line)
        line = "1) Back to main shop"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        menu_index = 2
        spell_options = []

        for s in spells_data:
            price = int(s.get("cost", 0))
            uses = int(s.get("uses", 1))
            line = f"{menu_index}) {s.get('name')} ({uses} uses) ({price}g)"
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            spell_options.append((menu_index, s))
            menu_index += 1
        line = ">"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        choice = (chooser("> ") if chooser else input("> ")).strip()
        if choice == "1":
            return
        elif choice.isdigit():
            idx = int(choice)
            for menu_idx, s in spell_options:
                if idx == menu_idx:
                    price = int(s.get("cost", 0))
                    uses = int(s.get("uses", 1))
                    if character.gold >= price:
                        character.gold -= price
                        name = s.get("name", "Spell")
                        character.spells[name] = character.spells.get(name, 0) + uses
                        msg = (
                            get_dialogue("shop", "buy", None, character)
                            or f"Purchased {name} (+{uses} uses)."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                        _emit(emitter, "state", gold=character.gold)
                    else:
                        msg = (
                            get_dialogue("shop", "no_gold", None, character)
                            or "Not enough gold."
                        )
                        if emitter:
                            _say(emitter, msg)
                        else:
                            print(msg)
                    break
        else:
            print(
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid choice."
            )


def sell_items(
    character: Character,
    weapons_data: list,
    armors_data: list,
    potions_data: list,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
    roller: Optional[Callable[[], int]] = None,
) -> None:
    # Compile sellable inventory items using shop data matches
    from .dice import roll_damage
    from math import ceil

    weapons_shop = weapons_data
    armors_shop = armors_data
    potions_shop = potions_data
    while True:
        line = f"{character.name} offers items to the shopkeeper to appraise."
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        msg = (
            get_npc_dialogue("shop", "sell_header", None, character)
            or "\n=== Sell Items ==="
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        sell_line = get_npc_dialogue("shop", "sell", None, character)
        gold_line = f"Gold: {character.gold}g"
        if emitter:
            _say(emitter, gold_line)
        else:
            print(gold_line)
        if sell_line:
            if emitter:
                _say(emitter, sell_line)
            else:
                print(sell_line)
        sell_options = []
        # Reserve 1 for Back to avoid colliding with item indices
        menu_idx = 2
        # Weapons
        for i, w in enumerate(character.weapons):
            entry = next(
                (
                    x
                    for x in weapons_shop
                    if x.get("name", "").lower() == w.name.lower()
                ),
                None,
            )
            if entry and int(entry.get("price", 0)) > 0:
                # Skip damaged weapons from being sellable
                if getattr(w, "damaged", False):
                    # show as not sellable in the list
                    sell_options.append(
                        (
                            menu_idx,
                            "weapon_damaged",
                            i,
                            int(entry.get("price", 0)),
                            w.name,
                        )
                    )
                else:
                    sell_options.append(
                        (menu_idx, "weapon", i, int(entry.get("price", 0)), w.name)
                    )
                menu_idx += 1
        # Armors owned
        for i, a in enumerate(character.armors_owned):
            entry = next(
                (x for x in armors_shop if x.get("name", "").lower() == a.name.lower()),
                None,
            )
            if entry and int(entry.get("price", 0)) > 0:
                # Skip damaged armor from sell list
                if getattr(a, "damaged", False):
                    sell_options.append(
                        (
                            menu_idx,
                            "armor_damaged",
                            i,
                            int(entry.get("price", 0)),
                            a.name,
                        )
                    )
                else:
                    sell_options.append(
                        (menu_idx, "armor", i, int(entry.get("price", 0)), a.name)
                    )
                menu_idx += 1
        # Potions
        for name, uses in {**character.potion_uses}.items():
            entry = next(
                (x for x in potions_shop if x.get("name", "").lower() == name.lower()),
                None,
            )
            if entry and int(entry.get("cost", entry.get("price", 0))) > 0 and uses > 0:
                price = int(entry.get("cost", entry.get("price", 0)))
                sell_options.append((menu_idx, "potion", name, price, name))
                menu_idx += 1
        if not sell_options:
            print(
                get_dialogue("shop", "no_sellable", None, character)
                or get_dialogue("shop", "none", None, character)
                or "You have nothing that can be sold in the shop."
            )
            return
        # Use NPC-prefixed dialogue for the sellable-items header so the shopkeeper's
        # name appears (e.g. "Mara: Sellable items:") instead of a generic system line.
        sell_header = get_npc_dialogue("shop", "sellable_items", None, character)
        text = sell_header or (
            get_dialogue("shop", "sellable_items", None, character)
            or "\nSellable items:"
        )
        if emitter:
            _say(emitter, text)
        else:
            print(text)
        # Print Back first so '1' is always Back and item indices follow after it.
        line = get_dialogue("shop", "back_main", None, character) or "1) Back"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        for mi in sell_options:
            label = mi[4]
            if mi[1] == "weapon_damaged" or mi[1] == "armor_damaged":
                label += " (damaged - cannot sell)"
            line = f"{mi[0]}) {label} (Shop price: {mi[3]}g)"
            if emitter:
                _say(emitter, line)
            else:
                print(line)
        prompt = get_dialogue("system", "enter", None, character) or ">"
        if emitter:
            _say(emitter, prompt)
        else:
            print(prompt)
        choice = (chooser("> ") if chooser else input("> ")).strip()
        if choice == "1":
            return
        if not choice.isdigit():
            msg = (
                get_dialogue("system", "invalid_choice", None, character)
                or get_dialogue("shop", "no_gold", None, character)
                or "Invalid selection."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)
            continue
        sel_idx = int(choice)
        choice_entry = next((x for x in sell_options if x[0] == sel_idx), None)
        if not choice_entry:
            msg = (
                get_dialogue("system", "invalid_choice", None, character)
                or get_dialogue("shop", "no_gold", None, character)
                or "Invalid selection."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)
            continue
        # Show method then confirm. First compute an appraisal so the player sees
        # the shop's offer before deciding to sell.
        category = choice_entry[1]
        orig_price = choice_entry[3]
        # If the chosen entry is marked damaged, refuse sale
        if category in ("weapon_damaged", "armor_damaged"):
            msg = (
                get_dialogue("shop", "cannot_sell_damaged", None, character)
                or "This item is damaged and cannot be sold. Repair it first at the weaponsmith."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)
            continue
        if category == "weapon":
            idx = choice_entry[2]
            item_name = character.weapons[idx].name
        elif category == "armor":
            idx = choice_entry[2]
            item_name = character.armors_owned[idx].name
        else:
            idx = choice_entry[2]
            item_name = idx
            # Non-equipment items (potions, etc.) may show an extra haggle blurb
            msg1 = (
                get_dialogue("shop", "haggle_confirm", None, character)
                or "Price will be determined based on your Charisma and luck."
            )
            msg2 = (
                get_dialogue("shop", "haggle_info", None, character)
                or f"Original shop price: {orig_price}g"
            )
            if emitter:
                _say(emitter, msg1)
                _say(emitter, msg2)
            else:
                print(msg1)
                print(msg2)

        # Appraise item (roll + Charisma influences final price). Show the
        # appraisal before asking for confirmation so the player can decide.
        appraisal_roll = int(roller()) if roller else roll_damage("5d4")
        cha = character.attributes.get("Charisma", 10)
        percent = (appraisal_roll + cha) * 0.025
        appraised_price = max(1, ceil(orig_price * percent))
        # Print appraisal/haggle success line (formatted if dialogue contains placeholders)
        haggle_success = get_dialogue("shop", "haggle_success", None, character)
        if haggle_success:
            try:
                text = haggle_success.format(
                    roll=appraisal_roll,
                    cha=cha,
                    percent=round(percent * 100, 1),
                    orig_price=orig_price,
                    price=appraised_price,
                )
            except Exception:
                text = haggle_success
        else:
            text = f"Sell roll: {appraisal_roll} + CHA({cha}) -> {round(percent*100,1)}% of {orig_price}g = {appraised_price}g"
        if emitter:
            _say(emitter, text)
        else:
            print(text)
        # Prevent selling equipped items
        if category == "weapon" and character.equipped_weapon_index == idx:
            msg = (
                get_dialogue("shop", "cannot_sell_equipped", None, character)
                or "You cannot sell an equipped weapon. Unequip it first."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)
            continue
        if (
            category == "armor"
            and character.armor
            and character.armor.name == item_name
        ):
            msg = (
                get_dialogue("shop", "cannot_sell_equipped", None, character)
                or "You cannot sell equipped armor. Unequip it first."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)
            continue
        # Prompt for confirmation explicitly so the player sees a prompt (web UI shows an input box)
        confirm_text = (
            get_dialogue("shop", "confirm_sale", None, character)
            or f"Confirm sale of {item_name} for appraisal? (y/n)"
        )
        try:
            text = confirm_text.format(name=item_name, price=appraised_price)
        except Exception:
            text = confirm_text
        if emitter:
            _say(emitter, text)
            _say(emitter, get_dialogue("system", "enter", None, character) or ">")
        else:
            print(text)
            print(get_dialogue("system", "enter", None, character) or ">")
        confirm = (chooser("> ") if chooser else input("> ")).strip().lower()
        if confirm not in ("y", "yes"):
            msg = (
                get_dialogue("shop", "sale_cancelled", None, character)
                or get_dialogue("shop", "none", None, character)
                or "Sale cancelled."
            )
            if emitter:
                _say(emitter, msg)
            else:
                print(msg)
            continue
        # Finalize sale using the appraised price
        price = appraised_price
        # remove
        if category == "weapon":
            removed = character.weapons.pop(idx)
            if character.equipped_weapon_index == idx:
                character.equipped_weapon_index = -1
            elif character.equipped_weapon_index > idx:
                character.equipped_weapon_index -= 1
            sold_msg = get_dialogue("shop", "sold_item", None, character)
            if sold_msg:
                try:
                    text = sold_msg.format(name=removed.name, price=price)
                except Exception:
                    text = sold_msg
                if emitter:
                    _say(emitter, text)
                else:
                    print(text)
            else:
                print(f"Sold {removed.name} for {price}g.")
            character.gold += price
            _emit(emitter, "state", gold=character.gold)
        elif category == "armor":
            removed = character.armors_owned.pop(idx)
            if character.armor and character.armor.name == removed.name:
                character.armor = None
            sold_msg = get_dialogue("shop", "sold_item", None, character)
            if sold_msg:
                try:
                    text = sold_msg.format(name=removed.name, price=price)
                except Exception:
                    text = sold_msg
                if emitter:
                    _say(emitter, text)
                else:
                    print(text)
            else:
                print(f"Sold {removed.name} for {price}g.")
            character.gold += price
            _emit(emitter, "state", gold=character.gold)
        else:
            pname = item_name
            if character.potion_uses.get(pname, 0) > 0:
                character.potion_uses[pname] -= 1
                if character.potion_uses[pname] <= 0:
                    del character.potion_uses[pname]
            elif character.potions > 0 and pname.lower() == "healing":
                character.potions -= 1
            sold_msg = get_dialogue("shop", "sold_item", None, character)
            if sold_msg:
                try:
                    text = sold_msg.format(name=pname, price=price)
                except Exception:
                    text = sold_msg
                if emitter:
                    _say(emitter, text)
                else:
                    print(text)
            else:
                msg = f"Sold {pname} for {price}g."
                if emitter:
                    _say(emitter, msg)
                else:
                    print(msg)
            character.gold += price
            _emit(emitter, "state", gold=character.gold)
