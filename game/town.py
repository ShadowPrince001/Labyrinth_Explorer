from __future__ import annotations

import random
from typing import Callable, Optional

from .dice import roll_damage
from .entities import Character
from .companion import name_companion, heal_companion
from .magic_items import remove_cursed_item
from .data_loader import get_dialogue, get_npc_dialogue


# Some frontends filter out lines containing 'choose', 'pick', 'select', or 'enter'.
# Provide a small helper to sanitize prompt text for instructions we want shown as plain text.
def _sanitize_instruction(text: str) -> str:
    if not text:
        return text
    import re

    # Map banned words to safe ASCII synonyms so the client won't filter the line.
    replacements = {
        "choose": "which",
        "pick": "option",
        "select": "which",
        "enter": "type",
    }

    def _repl(m: re.Match) -> str:
        w = m.group(0)
        low = w.lower()
        rep = replacements.get(low, w)
        # Preserve capitalization
        if w[0].isupper():
            return rep.capitalize()
        return rep

    sanitized = re.sub(r"\b(choose|pick|select|enter)\b", _repl, text, flags=re.I)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


# Minimal event emission helpers for gradual CLI → event-driven conversion.
def _emit(
    emitter: Optional[Callable[[dict], None]], event_type: str, **payload
) -> None:
    if emitter:
        evt = {"type": event_type}
        evt.update(payload)
        try:
            emitter(evt)
        except Exception:
            # Do not break gameplay if an emitter misbehaves
            pass


def _say(emitter: Optional[Callable[[dict], None]], text: str) -> None:
    _emit(emitter, "dialogue", text=text)


def healer(character: Character) -> None:
    # Flavor - prefix with NPC name when available
    print(
        get_npc_dialogue("town", "healer_elwen", None, character)
        or "Sister Elwen: The townsfolk heal your wounds and cleanse harmful effects."
    )
    character.hp = character.max_hp
    # Remove negative persistent effects
    for k in list(character.persistent_buffs.keys()):
        if k.startswith("debuff_"):
            character.persistent_buffs.pop(k, None)
    character.gold -= 20


def remove_curses(
    character: Character,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    """Remove curses from magic items via Sister Elwen.

    Emits:
    - dialogue: menu text and outcomes
    - state: updated gold when a curse is removed
    """
    cursed_items = [item for item in character.magic_items if item.cursed]
    if not cursed_items:
        # Use NPC-prefixed dialogue so the healer's name (Sister Elwen) appears
        msg = (
            get_npc_dialogue("town", "remove_curses_elwen", "no_curses", character)
            or "You have no cursed items."
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        return

    # Greeting / header
    header = (
        get_dialogue("town", "remove_curses_elwen", None, character)
        or "Cursed items found:"
    )
    if emitter:
        _say(emitter, header)
    else:
        print(header)

    for i, item in enumerate(cursed_items, 1):
        line = f"{i}) {item.name}"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
    back_line = f"{len(cursed_items) + 1}) Back"
    if emitter:
        _say(emitter, back_line)
    else:
        print(back_line)

    prompt = "Remove which curse? > "
    choice = chooser(prompt).strip() if chooser else input(prompt).strip()
    if not choice.isdigit():
        return
    idx = int(choice) - 1
    if idx == len(cursed_items):
        return
    if 0 <= idx < len(cursed_items):
        item = cursed_items[idx]
        # Flat cost to remove
        cost = 10
        if character.gold < cost:
            msg = get_dialogue("system", "not_enough_gold", None, character)
            if emitter:
                _say(emitter, msg or "Not enough gold.")
            else:
                print(msg or "Not enough gold.")
            return
        # Apply removal
        removed = False
        try:
            removed = remove_cursed_item(character, item.name)
        except Exception:
            # Fallback: just mark as not cursed if helper fails
            item.cursed = False
            removed = True
        character.gold -= cost
        if removed:
            done = (
                get_dialogue("items", "remove_cursed", None, character)
                or f"You remove the cursed {item.name}."
            )
            _say(emitter, done)
        _emit(emitter, "state", gold=character.gold)
        return


def side_quests(character: Character) -> None:
    """Town-side quest menu backed by the QuestManager."""
    from .quests import quest_manager

    while True:
        print(
            get_npc_dialogue("town", "town_bulletin", None, character)
            or "Town Bulletin: \n=== Side Quests ==="
        )
        # Load quests via manager so legacy dicts are normalized
        quests = []
        try:
            # manager exposes _load_existing but prefer generating a display list
            quests = [q for q in getattr(character, "side_quests", [])]
        except Exception:
            quests = []

        if not quests:
            print(
                get_dialogue("town", "town_bulletin", "none_available", character)
                or "You have no active side quests."
            )
        else:
            print("Current side quests:")
            for q in quests:
                try:
                    desc = q.get("desc", q.get("description", ""))
                    reward = q.get("reward", 0)
                    status = "Done" if q.get("completed") else "Active"
                    print(f"- {desc} - Reward: {reward}g ({status})")
                except Exception:
                    print(f"- {q}")

        # Menu options simplified: only Ask for New Side Quests and Back
        print("\n1) Ask for New Side Quests")
        print("2) Back")
        choice = input("> ").strip()
        if choice == "1":
            # Prevent asking if already at or above 3 active quests
            active_count = len([q for q in getattr(character, "side_quests", []) or []])
            if active_count >= 3:
                print(
                    get_dialogue("town", "too_many_quests", None, character)
                    or "You already have 3 active side quests. Complete some before asking for more."
                )
                continue
            # Generate up to fill to 3
            quest_manager.ask_for_new_quests(character, n=3)
            # Show only the newly persisted quests (they replace or append)
            new_list = getattr(character, "side_quests", []) or []
            # Show only the last N entries up to 3
            for q in new_list[-3:]:
                try:
                    desc = q.get("desc", q.get("description", "Unknown"))
                    reward = q.get("reward", 0)
                except Exception:
                    desc = getattr(q, "desc", getattr(q, "description", "Unknown"))
                    reward = getattr(q, "reward", 0)
                print(f"Quest Available: {desc} - reward: {reward}g")
            continue
        else:
            return


def train(
    character: Character,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    if character.trained_times >= 7:
        line = (
            get_npc_dialogue("town", "veteran_garron", None, character)
            or "Garron: You cannot train any further."
        )
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        return
    cost = 50 * (character.trained_times + 1)
    if character.gold < cost:
        line = (
            get_npc_dialogue("town", "veteran_garron", "no_gold", character)
            or f"Garron: Training costs {cost}g; you don't have enough."
        )
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        return
    header = (
        get_npc_dialogue("town", "veteran_garron", None, character)
        or "Garron: Choose an attribute to train:"
    )
    if emitter:
        _say(emitter, header)
    else:
        print(header)
    attrs = list(character.attributes.keys())
    # Show each attribute with the current value and the cost to train it
    for i, name in enumerate(attrs, 1):
        line = f"{i}) {name} ({character.attributes.get(name, 10)}) - Cost: {cost}g"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
    # Back option at the end (numbered after attributes)
    back_idx = len(attrs) + 1
    back_line = f"{back_idx}) Back"
    if emitter:
        _say(emitter, back_line)
    else:
        print(back_line)
    prompt = get_dialogue("system", "enter", None, character) or ">"
    if emitter:
        _say(emitter, prompt)
    else:
        print(prompt)
    raw = chooser("> ").strip() if chooser else input("> ").strip()
    # Handle Back explicitly
    if raw == str(back_idx):
        return
    try:
        i = int(raw) - 1
        if not (0 <= i < len(attrs)):
            raise ValueError()
        name = attrs[i]
    except Exception:
        msg = get_dialogue("system", "invalid_choice", None, character)
        if emitter:
            _say(emitter, msg or "Invalid choice.")
        else:
            print(msg or "Invalid choice.")
        return
    # Deduct cost and apply training
    character.gold -= cost
    character.attributes[name] = character.attributes.get(name, 10) + 1
    character.trained_times += 1
    msg = get_dialogue("town", "train_success", None, character)
    out = (
        msg.format(name=name, times=character.trained_times)
        if msg
        else f"You train {name}. It increases by 1. ({character.trained_times}/7)"
    )
    if emitter:
        _say(emitter, out)
    else:
        print(out)
    _emit(emitter, "state", gold=character.gold)


def rest(
    character: Character, emitter: Optional[Callable[[dict], None]] = None
) -> None:
    # Only allow one roll-based rest attempt while in town. This resets when entering/exiting the labyrinth.
    if getattr(character, "rest_attempted", False):
        msg = get_dialogue("town", "rest_again_fail", None, character)
        if emitter:
            _say(emitter, msg or "You try to rest again but fail to get a good rest.")
        else:
            print(msg or "You try to rest again but fail to get a good rest.")
        return
    intro = get_dialogue("town", "rest_short", None, character) or "You take a rest..."
    if emitter:
        _say(emitter, intro)
    else:
        print(intro)
    con = character.attributes.get("Constitution", 10)
    bonus = 2 if con >= 15 else (1 if con >= 12 else 0)
    roll = random.randint(1, 20) + bonus
    character.rest_attempted = True
    if roll >= 12:
        heal = roll_damage("2d6")
        character.hp = min(character.max_hp, character.hp + heal)
        msg = get_dialogue("town", "rest_heal", None, character)
        out = msg.format(heal=heal) if msg else f"You rest well and heal {heal} HP."
        if emitter:
            _say(emitter, out)
        else:
            print(out)
    else:
        msg = get_dialogue("town", "rest_fail", None, character)
        out = msg or "You fail to get a good rest."
        if emitter:
            _say(emitter, out)
        else:
            print(out)

    _emit(emitter, "state", hp=character.hp, gold=character.gold)


def weaponsmith(
    character: Character,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
) -> None:
    # Greet the player by name and show their current gold before listing services
    intro = f"{character.name} approaches the weaponsmith."
    if emitter:
        _say(emitter, intro)
    else:
        print(intro)
    # Use get_npc_dialogue to pick a single Thorin line and prefix with his name
    greet = (
        get_npc_dialogue("town", "weaponsmith_thorin", None, character)
        or "Thorin: === Weaponsmith ==="
    )
    if emitter:
        _say(emitter, greet)
    else:
        print(greet)
    # Neutral gold display
    gold_line = f"Gold: {character.gold}g"
    if emitter:
        _say(emitter, gold_line)
    else:
        print(gold_line)
    damaged_weapons = [w for w in character.weapons if getattr(w, "damaged", False)]
    damaged_armors = [
        a
        for a in (
            character.armors_owned + ([character.armor] if character.armor else [])
        )
        if a and getattr(a, "damaged", False)
    ]
    if not damaged_weapons and not damaged_armors:
        # Show a single no-damaged line from Thorin (or fallback system message)
        msg = get_npc_dialogue(
            "town", "weaponsmith_thorin", "no_damaged", character
        ) or get_dialogue("town", "no_damaged_equipment", None, character)
        out = msg or "Thorin: All your equipment is in good condition."
        if emitter:
            _say(emitter, out)
        else:
            print(out)
        return
    # Display damaged equipment menu
    idx_map = []
    ctr = 1
    # Flat repair cost (can be tuned later)
    cost = 30
    if damaged_weapons:
        msg = get_dialogue("town", "damaged_weapons", None, character)
        line = msg or "Damaged weapons:"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        for w in damaged_weapons:
            msg = get_dialogue("town", "damaged_weapon_option", None, character)
            line = (
                msg.format(idx=ctr, name=w.name, cost=cost)
                if msg
                else f"{ctr}) {w.name} (reduced effectiveness)"
            )
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            idx_map.append(("weapon", w))
            ctr += 1
    if damaged_armors:
        msg = get_dialogue("town", "damaged_armors", None, character)
        line = msg or "Damaged armor:"
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        for a in damaged_armors:
            msg = get_dialogue("town", "damaged_armor_option", None, character)
            line = (
                msg.format(idx=ctr, name=a.name, cost=cost)
                if msg
                else f"{ctr}) {a.name} (reduced protection)"
            )
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            idx_map.append(("armor", a))
            ctr += 1
    msg = get_dialogue("town", "back_option", None, character)
    back_line = msg.format(idx=ctr) if msg else f"{ctr}) Back"
    if emitter:
        _say(emitter, back_line)
    else:
        print(back_line)
    prompt = get_dialogue("system", "enter", None, character) or ">"
    if emitter:
        _say(emitter, prompt)
    else:
        print(prompt)
    choice = chooser("> ").strip() if chooser else input("> ").strip()
    if not choice.isdigit():
        return
    idx = int(choice) - 1
    if idx == len(idx_map):
        return
    if 0 <= idx < len(idx_map):
        type_, obj = idx_map[idx]
        cost = 30
        if character.gold < cost:
            msg = get_dialogue("town", "repair_costs", None, character)
            out = (
                msg.format(cost=cost)
                if msg
                else f"Repair costs {cost}g; you don't have enough."
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
            return
        character.gold -= cost
        if type_ == "weapon":
            if hasattr(obj, "damaged"):
                obj.damaged = False
            msg = get_dialogue("town", "repair_success_weapon", None, character)
            out = (
                msg.format(name=obj.name, cost=cost)
                if msg
                else f"Your {obj.name} has been repaired! (Cost: {cost}g)"
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
        else:
            if hasattr(obj, "damaged"):
                obj.damaged = False
            msg = get_dialogue("town", "repair_success_armor", None, character)
            out = (
                msg.format(name=obj.name, cost=cost)
                if msg
                else f"Your {obj.name} has been repaired and will restore protection. (Cost: {cost}g)"
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
        _emit(emitter, "state", gold=character.gold)


def companion_menu(character: Character) -> None:
    while True:
        print(
            get_dialogue("system", "companion_header", None, character)
            or "\n=== Companion ==="
        )
        opts = get_dialogue("system", "companion_options", None, character)
        if opts:
            print(opts)
        else:
            print(get_dialogue("companion", "companion_menu", None, character))
        choice = input("> ").strip()
        if choice == "1":
            new_name = input(
                get_dialogue("system", "companion_enter_name", None, character)
                or "Enter new name: "
            ).strip()
            if new_name:
                name_companion(character, new_name)
        elif choice == "2":
            heal_companion(character)
        elif choice == "3":
            return
        else:
            msg = get_dialogue("system", "invalid_choice", None, character)
            print(msg or "Invalid choice.")


def gambling(
    character: Character,
    emitter: Optional[Callable[[dict], None]] = None,
    chooser: Optional[Callable[[str], str]] = None,
    roller: Optional[Callable[[int], int]] = None,
) -> None:
    """Enhanced gambling: guess-the-dice with multiple modes.

    Modes:
     - 1) Guess exact number (2-12) — highest return (11x) for exact hit.
     - 2) Guess range of roll 2d10 (we'll emulate a 2-10+10? see below) mapped to:
             ranges: 1-5, 6-10, 11-15, 16-20 (these are abstract ranges — odds set accordingly).

    Bet flow:
     - Player chooses mode, then chooses an amount (min 5g) or Back before selecting amount.
     - Quick-increment buttons allowed (+5, +10, +50, +100) while selecting amount (simulated via input tokens).

    Payouts are calculated from odds (simplified): payout = bet * multiplier - bet (net gain shown as reward in message).

    Note: This function keeps dialogue lines from gambler_seth and uses get_dialogue for messages.
    """
    # Mode selection: only three buttons (Exact, Range, Back)
    line = (
        get_npc_dialogue("town", "gambler_seth", None, character)
        or "Seth: Feeling lucky? Choose a mode."
    )
    if emitter:
        _say(emitter, line)
    else:
        print(line)
    # Plain text prompt (frontend prefers plain lines for instructions)
    mode_prompt = (
        get_dialogue("system", "choose_mode_prompt", None, character)
        or "Which mode do you want to play?"
    )
    msg = _sanitize_instruction(mode_prompt)
    if emitter:
        _say(emitter, msg)
        _say(emitter, "")
        _say(emitter, "1) Exact guess")
        _say(emitter, "2) Range guess")
        _say(emitter, "3) Back")
    else:
        print(msg)
        print("")
        print("1) Exact guess")
        print("2) Range guess")
        print("3) Back")
    sel = (chooser("> ") if chooser else input("> ")).strip().lower()
    if sel in ("3", "back", "b"):
        return
    if sel in ("1", "exact"):
        mode = "exact"
    elif sel in ("2", "range"):
        mode = "range"
    else:
        out = (
            get_dialogue("system", "invalid_choice", None, character)
            or "Invalid choice."
        )
        if emitter:
            _say(emitter, out)
        else:
            print(out)
        return

    # Helper for bet selection using buttons (+5 +10 +100 / ok / back)
    def choose_bet(bet: int = 0) -> int | None:
        min_bet = 5
        # Loop until the user confirms with OK or goes back
        while True:
            # Re-print the instructions each loop so UI frontends that parse printed options
            # will always see the available choices after an increment. Emit as numbered
            # so simple parsers show it.
            bet_prompt = (
                get_dialogue("town", "haggle_info", None, character)
                or f"Which bet would you like? Minimum {min_bet}g."
            )
            if emitter:
                _say(emitter, bet_prompt)
                _say(emitter, "1) +5")
                _say(emitter, "2) +10")
                _say(emitter, "3) +100")
                _say(emitter, "4) OK")
                _say(emitter, "5) Back")
                _say(emitter, f"Current bet: {bet}g")
                inp = (chooser("> ") if chooser else input("> ")).strip().lower()
            else:
                print(bet_prompt)
                print("1) +5")
                print("2) +10")
                print("3) +100")
                print("4) OK")
                print("5) Back")
                print(f"Current bet: {bet}g")
                inp = (chooser("> ") if chooser else input("> ")).strip().lower()
            # Back option - return None to indicate cancel
            if inp in ("back", "b", "5"):
                return None
            # Confirm bet
            if inp in ("ok", "4"):
                if bet < min_bet:
                    out = (
                        get_dialogue("town", "bet_range", None, character)
                        or f"Bet must be at least {min_bet}g."
                    )
                    if emitter:
                        _say(emitter, out)
                    else:
                        print(out)
                    return
                if bet > character.gold:
                    out = (
                        get_dialogue("town", "bet_range", None, character)
                        or "You don't have enough gold to cover that bet."
                    )
                    if emitter:
                        _say(emitter, out)
                    else:
                        print(out)
                    return
                return bet
            # Map numeric button presses to increments
            if inp in ("1", "+5"):
                bet += 5
                continue
            if inp in ("2", "+10"):
                bet += 10
                continue
            if inp in ("3", "+100"):
                bet += 100
                continue
            # allow typing a number directly then confirm with ok
            try:
                val = int(inp)
            except Exception:
                out = (
                    get_dialogue("town", "invalid_bet", None, character)
                    or "Invalid bet."
                )
                if emitter:
                    _say(emitter, out)
                else:
                    print(out)
                continue
            bet = val

    # Helper roll
    def roll_d_sides(sides: int) -> int:
        if roller:
            return int(roller(sides))
        return random.randint(1, sides)

    # Exact guess mode
    if mode == "exact":
        # Die selection with three options printed one-per-line
        line = (
            get_npc_dialogue("town", "gambler_seth", None, character)
            or "Seth: Such confidence! Let's see if Lady Luck agrees."
        )
        if emitter:
            _say(emitter, line)
        else:
            print(line)
        # Clarify next step for the player/UI — put it as a numbered option so the
        # frontend shows it alongside the die choices.
        odds_prompt = (
            get_dialogue("system", "choose_odds_prompt", None, character)
            or "Which odds would you like?"
        )
        msg = _sanitize_instruction(odds_prompt)
        if emitter:
            _say(emitter, msg)
            _say(emitter, "")
            _say(emitter, "1) D20")
            _say(emitter, "2) D10")
            _say(emitter, "3) D6")
            _say(emitter, "4) Back")
        else:
            print(msg)
            print("")
            print("1) D20")
            print("2) D10")
            print("3) D6")
            print("4) Back")
        die_sel = (chooser("> ") if chooser else input("> ")).strip().lower()
        if die_sel in ("back", "b", "4"):
            # Restart gambling menu
            return gambling(character, emitter=emitter, chooser=chooser, roller=roller)
        if die_sel in ("1", "d20"):
            sides = 20
        elif die_sel in ("2", "d10"):
            sides = 10
        elif die_sel in ("3", "d6"):
            sides = 6
        else:
            out = (
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid die choice."
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
            return

        # Choose bet (start at 0). If cancelled, return to gambling menu
        bet = choose_bet(0)
        if bet is None:
            return

        # Allow picking a number (present compact buttons where feasible)
        # Print each possible pick on its own line so frontends can parse them as separate options
        for i in range(1, sides + 1):
            line = f"{i}) {i}"
            if emitter:
                _say(emitter, line)
            else:
                print(line)
        # Prompt explicitly before input so UI frontends pick it up
        pick_prompt = (
            get_dialogue("town", "pick_number", None, character)
            or f"Which number (1-{sides})?"
        )
        msg = _sanitize_instruction(pick_prompt)
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        pick = (chooser("> ") if chooser else input("> ")).strip().lower()
        if pick in ("back", "b"):
            return
        try:
            pick_num = int(pick)
        except Exception:
            out = (
                get_dialogue("town", "invalid_bet", None, character)
                or "Invalid number."
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
            return
        if not (1 <= pick_num <= sides):
            out = (
                get_dialogue("town", "invalid_bet", None, character)
                or f"Number must be between 1 and {sides}."
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
            return

        # Roll and resolve
        roll = roll_d_sides(sides)
        # Print what the player picked and what the roll was. Use dialogue template when available.
        pick_msg = f"You chose {pick_num}."
        raw = get_dialogue("system", "you_rolled", None, character)
        if raw:
            # Safely format templates that expect {roll} or similar
            try:
                print(raw.format(roll=roll))
            except Exception:
                print(raw)
            # Also print the explicit pick so it's always visible
            if emitter:
                _say(emitter, pick_msg)
            else:
                print(pick_msg)
        else:
            line1 = f"You rolled {roll}!"
            if emitter:
                _say(emitter, line1)
                _say(emitter, pick_msg)
            else:
                print(line1)
                print(pick_msg)
        if roll == pick_num:
            multiplier = int(sides / 1.5)
            payout = int(bet * multiplier)
            character.gold += payout
            # Summary: only state the win amount (roll/pick already printed above)
            line = f"Result: You win {payout}g."
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            msg = get_dialogue("town", "gamble_win", None, character)
            if msg:
                if emitter:
                    _say(emitter, msg)
                else:
                    print(msg)
        else:
            # Player loses the bet
            character.gold -= bet
            line = f"Result: You lose {bet}g."
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            msg = get_dialogue("town", "gamble_lose", None, character)
            if msg:
                if emitter:
                    _say(emitter, msg)
                else:
                    print(msg)
        _emit(emitter, "state", gold=character.gold)
        return

    # Range guess mode
    if mode == "range":
        pick_range = (
            get_dialogue("system", "pick_range_prompt", None, character)
            or "Which range would you like?"
        )
        msg = _sanitize_instruction(pick_range)
        if emitter:
            _say(emitter, msg)
            for line in ("1) 1-5", "2) 6-10", "3) 11-15", "4) 16-20", "5) Back"):
                _say(emitter, line)
        else:
            print(msg)
            print("1) 1-5")
            print("2) 6-10")
            print("3) 11-15")
            print("4) 16-20")
            print("5) Back")
        rsel = (chooser("> ") if chooser else input("> ")).strip().lower()
        if rsel in ("back", "b", "5"):
            # restart gambling menu
            return gambling(character, emitter=emitter, chooser=chooser, roller=roller)
        ranges = {
            "1": range(1, 6),
            "2": range(6, 11),
            "3": range(11, 16),
            "4": range(16, 21),
            "1-5": range(1, 6),
            "6-10": range(6, 11),
            "11-15": range(11, 16),
            "16-20": range(16, 21),
        }
        if rsel not in ranges:
            out = (
                get_dialogue("system", "invalid_choice", None, character)
                or "Invalid range choice."
            )
            if emitter:
                _say(emitter, out)
            else:
                print(out)
            return

        chosen_range = ranges[rsel]
        # Human-readable text for the chosen range (e.g., '1-5')
        if rsel in ("1", "1-5"):
            chosen_range_text = "1-5"
        elif rsel in ("2", "6-10"):
            chosen_range_text = "6-10"
        elif rsel in ("3", "11-15"):
            chosen_range_text = "11-15"
        elif rsel in ("4", "16-20"):
            chosen_range_text = "16-20"
        else:
            # fallback to a computed representation
            chosen_range_text = f"{min(chosen_range)}-{max(chosen_range)}"

        # Choose bet
        bet = choose_bet(0)
        if bet is None:
            return

        # Roll d20 and resolve
        roll = roll_d_sides(20)
        if roll in chosen_range:
            payout = int(bet * 3)
            character.gold += payout
            # Show roll and chosen range in the win summary for clarity
            line1 = f"You rolled {roll}. You chose range {chosen_range_text}."
            line2 = f"Result: You win {payout}g."
            if emitter:
                _say(emitter, line1)
                _say(emitter, line2)
            else:
                print(line1)
                print(line2)
            msg = get_dialogue("town", "gamble_win", None, character)
            if msg:
                if emitter:
                    _say(emitter, msg)
                else:
                    print(msg)
        else:
            character.gold -= bet
            # Include chosen range and roll in the concise result for clarity
            line = f"Result: You rolled {roll}. You chose range {chosen_range_text}. You lose {bet}g."
            if emitter:
                _say(emitter, line)
            else:
                print(line)
            msg = get_dialogue("town", "gamble_lose", None, character)
            if msg:
                if emitter:
                    _say(emitter, msg)
                else:
                    print(msg)
        _emit(emitter, "state", gold=character.gold)
        return


def eat_meal(
    character: Character, emitter: Optional[Callable[[dict], None]] = None
) -> None:
    """Simple meal in town: restores a modest amount of HP.

    Events emitted (when emitter provided):
    - dialogue: meal result text
    - state: updated character snapshot (hp, gold)
    """
    msg = get_dialogue("town", "eat_meal", None, character)
    text = msg or "You eat a hearty meal and feel better. You heal 10 HP."
    if emitter:
        _say(emitter, text)
    else:
        print(text)
    heal = 10
    character.hp = min(character.max_hp, character.hp + heal)
    character.gold = max(0, character.gold - 2)
    _emit(emitter, "state", hp=character.hp, gold=character.gold)


def tavern_drink(
    character: Character, emitter: Optional[Callable[[dict], None]] = None
) -> None:
    """Have a drink — small random effects (flavor).

    Events emitted:
    - dialogue: bartender line and outcome
    - state: updated hp/gold
    """
    msg = get_npc_dialogue("town", "bartender_roth", None, character)
    text = msg or "You sit at the tavern and order a drink."
    if emitter:
        _say(emitter, text)
    else:
        print(text)
    # Small random flavor: either heal 5-10 HP or just chatter
    roll = random.randint(1, 6)
    if roll <= 3:
        heal = random.randint(5, 10)
        character.hp = min(character.max_hp, character.hp + heal)
        out = (
            get_dialogue("town", "drink_heal", None, character)
            or f"You share a restorative brew and recover {heal} HP."
        )
        _say(emitter, out)
    else:
        out = (
            get_dialogue("town", "drink_talk", None, character)
            or "You trade stories with the locals."
        )
        _say(emitter, out)
    character.gold = max(0, character.gold - 5)
    _emit(emitter, "state", hp=character.hp, gold=character.gold)


def praying(
    character: Character, emitter: Optional[Callable[[dict], None]] = None
) -> None:
    """Pray at the shrine — minor healing or morale boost."""
    # One-time use per town visit
    if getattr(character, "prayed", False):
        msg = (
            get_dialogue("system", "prayed_already", None, character)
            or "You've already prayed recently."
        )
        if emitter:
            _say(emitter, msg)
        else:
            print(msg)
        return

    msg = (
        get_npc_dialogue("town", "priestess_eira", None, character)
        or "You kneel and offer a prayer."
    )
    if emitter:
        _say(emitter, msg)
    else:
        print(msg)
    # small heal
    heal = 10
    wis = character.attributes.get("Wisdom", 10)
    if wis >= 15:
        bonus = 5
    elif wis >= 12:
        bonus = 3
    elif wis >= 10:
        bonus = 1
    else:
        bonus = 0
    # Apply the heal immediately (minor)
    character.hp = min(character.max_hp, character.hp + heal)
    # Roll with wisdom bonus to determine stronger effect
    roll = random.randint(1, 20) + bonus
    if roll > 15:
        out = (
            get_dialogue("town", "praying_heal", None, character)
            or "Your prayer is answered. You feel renewed."
        )
        _say(emitter, out)
    else:
        out = (
            get_dialogue("town", "praying_fail", None, character)
            or "Your prayer goes unanswered."
        )
        _say(emitter, out)
    # Mark as used for this visit
    character.prayed = True
    _emit(emitter, "state", hp=character.hp, gold=character.gold)
