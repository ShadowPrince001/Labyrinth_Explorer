"""
Event-driven Game Engine for Labyrinth Adventure

This module replaces CLI print/input flows with a structured event system
that the web backend can drive. All game logic remains in Python and lives
in the game/ package. The engine exposes a small API:

- engine.start(): initialize and emit the main menu
- engine.handle_action(action: str, payload: dict | None): advance state

It emits events as dictionaries, for example:
  {"type": "message", "text": "..."}
  {"type": "choices", "items": [{"id": "1", "label": "New Game"}, ...]}
  {"type": "prompt", "id": "name", "label": "Enter your name"}
  {"type": "state", "data": { ... snapshot ... }}

Backends (Flask-SocketIO) forward these to the client. The frontend renders
the log and choices, and replies with actions like {type: 'choose', id: '1'}

Note: This is a first pass focusing on core flows (main menu, character
creation, town, labyrinth scaffold). Combat and advanced town (gambling, spells,
etc.) can be added by following the same pattern: compute results, then emit
message/choices/prompt events. Keep text content identical to the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
import random
import math

from .entities import Character, Monster
from .dice import roll_damage
from .combat import compute_armor_class, wisdom_bonus
from .labyrinth import generate_room
from .data_loader import (
    get_dialogue,
    load_dialogues,
    load_weapons,
    load_armors,
    load_potions,
    load_spells,
)
from .traps import random_room_trap, resolve_trap_events


# ---------- Event and Engine State ----------

Event = Dict[str, Any]


@dataclass
class EngineState:
    phase: str = (
        "main_menu"  # main_menu | create_name | create_attrs | town | dungeon | combat
    )
    subphase: str = ""  # for phase-specific steps
    buffer: List[Event] = field(default_factory=list)
    # Character and world
    character: Optional[Character] = None
    depth: int = 1
    current_room: Optional[Dict[str, Any]] = None
    # Track navigation history to support step-wise backtracking
    room_history: List[int] = field(default_factory=list)
    # Track total monster encounters for milestone spawns
    monster_encounters: int = 0
    # Combat runtime state
    combat: Dict[str, Any] = field(default_factory=dict)
    # Mini-states for town features
    gamble: Dict[str, Any] = field(default_factory=dict)
    # Character creation
    pending_attrs: List[str] = field(
        default_factory=lambda: [
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ]
    )
    assignments: Dict[str, int] = field(default_factory=dict)
    pending_roll: Optional[int] = None
    # Track last attribute assignment for recap
    last_assignment: Optional[Tuple[str, int]] = None
    # Difficulty selection (affects stat rolling only)
    difficulty: str = "normal"  # "easy" | "normal" | "hard"


class GameEngine:
    # Difficulty configuration: modular design for easy expansion
    DIFFICULTY_CONFIG = {
        "easy": {
            "name": "Easy",
            "dice": "6d5",
            "description": "Higher starting stats for a gentler experience.",
        },
        "normal": {
            "name": "Normal",
            "dice": "5d5",
            "description": "Balanced starting stats for the intended experience.",
        },
        "hard": {
            "name": "Hard",
            "dice": "4d5",
            "description": "Lower starting stats for a challenging experience.",
        },
    }

    def __init__(self):
        self.s = EngineState()
        # Gate verbose prints behind a flag; set True only when actively debugging
        self.debug: bool = False

    def _get_stat_roll_dice(self) -> str:
        """Get the dice formula based on selected difficulty."""
        config = self.DIFFICULTY_CONFIG.get(
            self.s.difficulty, self.DIFFICULTY_CONFIG["normal"]
        )
        return config["dice"]

    # ----- public API -----
    def start(self) -> List[Event]:
        self.s.buffer.clear()
        # Clear screen like the CLI and show header
        self._emit_clear()
        # Show labyrinth background on main menu
        try:
            from .scene_manager import set_labyrinth_background

            ev = set_labyrinth_background()
            bg = ev.get("data", {}).get("background") if isinstance(ev, dict) else None
            if bg:
                self._emit_scene(bg)
            else:
                self._emit_scene("labyrinth.png")
        except Exception:
            self._emit_scene("labyrinth.png")
        hdr = (
            get_dialogue("system", "main_menu_header", None, None)
            or "=== Labyrinth Adventure (CLI) ==="
        )
        self._emit_dialogue(hdr)
        # Use fixed numbering to avoid duplicate numbers from dialogues
        self._emit_menu(
            [
                ("main:new", "1) New Game"),
                ("main:load", "2) Load Game"),
                ("main:howto", "3) How to Play"),
                ("main:quit", "4) Quit"),
            ]
        )
        self._emit_state()
        return self._flush()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "phase": self.s.phase,
            "depth": self.s.depth,
            "character": self.s.character.to_dict() if self.s.character else None,
        }

    def load_snapshot(self, data: Dict[str, Any]) -> bool:
        """Load a previously saved minimal snapshot. Returns True on success.

        Expected shape:
          { "phase": str, "depth": int, "character": {...} }
        """
        try:
            if not isinstance(data, dict):
                return False
            depth = int(data.get("depth", 1))
            ch = data.get("character")
            from .entities import Character as _Char

            char = _Char.from_dict(ch) if isinstance(ch, dict) else None

            # Apply to engine state (normalize to town for safety)
            self.s.buffer.clear()
            self.s.character = char
            self.s.depth = max(1, depth)
            self.s.phase = "town" if char else "main_menu"
            self.s.subphase = ""
            self.s.current_room = None
            self.s.room_history = []
            self.s.monster_encounters = 0
            self.s.combat = {}
            self.s.gamble = {}
            # Clear utilities preview/flags
            try:
                setattr(self.s, "used_divine_depth", None)
                setattr(self.s, "used_listen_depth", None)
                setattr(self.s, "next_forced_monster", None)
                setattr(self.s, "peek_next", None)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def handle_action(
        self, action: str, payload: Optional[Dict[str, Any]] = None
    ) -> List[Event]:
        import sys

        if self.debug:
            print(f"\n{'='*60}")
            print("[ENGINE] handle_action called")
            print(f"[ENGINE] action={action}")
            print(f"[ENGINE] current phase={self.s.phase}, subphase={self.s.subphase}")
            sys.stdout.flush()

        self.s.buffer.clear()
        payload = payload or {}

        # Main menu
        if self.s.phase == "main_menu":
            return self._handle_main_menu(action)

        # Difficulty selection
        if self.s.phase == "select_difficulty":
            return self._handle_difficulty_selection(action)

        # Character creation
        if self.s.phase == "create_name":
            return self._handle_create_name(action, payload)
        if self.s.phase == "create_attrs":
            return self._handle_create_attrs(action)

        # Town
        if self.s.phase == "town":
            return self._handle_town(action, payload)
        if self.s.phase == "shop":
            return self._handle_shop(action)
        if self.s.phase == "inventory":
            return self._handle_inventory(action)

        # Labyrinth (internal phase retained as 'dungeon' for save/compat)
        if self.s.phase == "dungeon":
            return self._handle_dungeon(action)

        # Combat (placeholder scaffold)
        if self.s.phase == "combat":
            return self._handle_combat(action)

        # Fallback
        self._emit_dialogue(f"Unknown action in phase {self.s.phase}: {action}")
        self._emit_state()
        return self._flush()

    # ----- handlers -----
    def _handle_difficulty_selection(self, action: str) -> List[Event]:
        """Handle difficulty selection screen."""
        if action.startswith("difficulty:"):
            difficulty = action.split(":", 1)[1]
            if difficulty in self.DIFFICULTY_CONFIG:
                self.s.difficulty = difficulty
                # Now show the story intro
                self.s.phase = "main_menu"
                self.s.subphase = "intro:story"
                self._emit_clear()
                # Ensure labyrinth background is set at the start of character creation
                try:
                    from .scene_manager import set_labyrinth_background

                    ev = set_labyrinth_background()
                    bg = (
                        ev.get("data", {}).get("background")
                        if isinstance(ev, dict)
                        else None
                    )
                    if bg:
                        self._emit_scene(bg)
                    else:
                        self._emit_scene("labyrinth.png")
                except Exception:
                    self._emit_scene("labyrinth.png")
                try:
                    d = load_dialogues() or {}
                    sysd = d.get("system", {}) if isinstance(d, dict) else {}
                    story = []
                    if isinstance(sysd.get("story_intro", {}), dict):
                        story = list(
                            sysd.get("story_intro", {}).get("dialogues", []) or []
                        )
                    for line in story:
                        if line:
                            self._emit_dialogue(line)
                except Exception:
                    self._emit_dialogue(
                        "In a world scarred by ancient betrayals, mysterious labyrinths spawn from wounds in reality itself..."
                    )
                self._emit_pause()
                self._emit_menu([("intro:continue", "Continue")])
            else:
                self._emit_dialogue(f"Invalid difficulty: {difficulty}")
                self._emit_state()
        else:
            # Show difficulty selection screen (compact, mobile-friendly)
            self._emit_clear()
            self._emit_dialogue("       SELECT YOUR DIFFICULTY LEVEL        ")
            self._emit_dialogue("═══════════════════════════════════════════")

            # EASY
            self._emit_dialogue("▶ EASY ")
            self._emit_dialogue("  Roll 6d5 (6-30 range) for each attribute.")
            # NORMAL
            self._emit_dialogue("▶ NORMAL ")
            self._emit_dialogue("  Roll 5d5 (5-25 range) for each attribute.")
            # HARD
            self._emit_dialogue("▶ HARD")
            self._emit_dialogue("  Roll 4d5 (4-20 range) for each attribute.")

            self._emit_dialogue("This choice affects your starting attributes only.")
            self._emit_dialogue(
                "You cannot change difficulty once character creation begins."
            )
            self._emit_state()
            self._emit_menu(
                [
                    ("difficulty:easy", "Easy (6d5)"),
                    ("difficulty:normal", "Normal (5d5)"),
                    ("difficulty:hard", "Hard (4d5)"),
                ]
            )

        return self._flush()

    def _handle_main_menu(self, action: str) -> List[Event]:
        if action == "main:new":
            # Go to difficulty selection screen
            self.s.phase = "select_difficulty"
            self.s.subphase = ""
            return self._handle_difficulty_selection("")
        elif action == "intro:continue" and (self.s.subphase or "").startswith(
            "intro:"
        ):
            if self.s.subphase == "intro:story":
                # Stage 2: Show full startup
                self._emit_clear()
                try:
                    d = load_dialogues() or {}
                    sysd = d.get("system", {}) if isinstance(d, dict) else {}
                    startup = []
                    if isinstance(sysd.get("startup", {}), dict):
                        startup = list(
                            sysd.get("startup", {}).get("dialogues", []) or []
                        )
                    for line in startup:
                        if line:
                            self._emit_dialogue(line)
                except Exception:
                    self._emit_dialogue(
                        "So you seek to become an Explorer? Few attempt this path..."
                    )
                self._emit_pause()
                self.s.subphase = "intro:startup"
                self._emit_menu([("intro:continue", "Continue")])
            else:
                # Stage 3: Ask name
                self._emit_clear()
                self.s.phase = "create_name"
                self.s.subphase = ""
                ask = (
                    get_dialogue("system", "ask_name", None, None)
                    or "What is your name?"
                )
                self._emit_dialogue(ask)
                self._emit_prompt("name", "Enter your name:")
                self._emit_menu([("prompt:submit", "OK")])
        elif action == "main:howto":
            # Show a concise "How to Play" screen (<=10 lines)
            self._emit_clear()
            # Keep labyrinth background while reading
            try:
                from .scene_manager import set_labyrinth_background

                ev = set_labyrinth_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
            except Exception:
                pass
            lines = [
                "▶ Welcome to Labyrinth Adventure, a turn-based dungeon crawler.",
                "▶ Select your difficulty: Easy, Normal, or Hard to set your starting stats.",
                "▶ Explore the town to shop, rest, train, and manage your inventory.",
                "▶ Enter the labyrinth, where rooms, traps, and monsters await.",
                "▶ Use your skills wisely—attack, cast spells, drink potions, or charm foes.",
                "▶ Winning combats grants XP and treasure; charm foes for partial rewards.",
                "▶ Keep an eye on your health, potions, and gold carefully.",
                "▶ Examine monsters to learn their weaknesses before attacking.",
                "▶ Save your progress often and return to town when needed.",
                "▶ Your choices determine your fate—survive and conquer the labyrinth!",
            ]
            for ln in lines:
                self._emit_dialogue(ln)
            self._emit_menu([("main:menu", "Back")])
            self._emit_state()
            return self._flush()
        elif action == "main:menu":
            # Re-render main menu
            self._emit_clear()
            # Set labyrinth background again for consistency
            try:
                from .scene_manager import set_labyrinth_background

                ev = set_labyrinth_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
            except Exception:
                pass
            hdr = (
                get_dialogue("system", "main_menu_header", None, None)
                or "=== Labyrinth Adventure (CLI) ==="
            )
            self._emit_dialogue(hdr)
            self._emit_menu(
                [
                    ("main:new", "1) New Game"),
                    ("main:load", "2) Load Game"),
                    ("main:howto", "3) How to Play"),
                    ("main:quit", "4) Quit"),
                ]
            )
            self._emit_state()
            return self._flush()
        elif action == "main:load":
            self._emit_dialogue("No saved game found.")
            self._emit_menu(
                [
                    ("main:new", "New Game"),
                    ("main:menu", "Back"),
                ]
            )
        elif action == "main:quit":
            # On quit, reset background to labyrinth
            try:
                from .scene_manager import set_labyrinth_background

                ev = set_labyrinth_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
                else:
                    self._emit_scene("labyrinth.png")
            except Exception:
                self._emit_scene("labyrinth.png")
            self._emit_dialogue("Thanks for playing!")
            self._emit_menu([])
        else:
            # repeat menu with fixed numbering
            self._emit_menu(
                [
                    ("main:new", "1) New Game"),
                    ("main:load", "2) Load Game"),
                    ("main:howto", "3) How to Play"),
                    ("main:quit", "4) Quit"),
                ]
            )
        self._emit_state()
        return self._flush()

    def _handle_create_name(self, action: str, payload: Dict[str, Any]) -> List[Event]:
        if action != "prompt:submit":
            # re-show prompt
            self._emit_prompt("name", "Enter your name:")
            self._emit_menu([("prompt:submit", "OK")])
            self._emit_state()
            return self._flush()

        name = (payload.get("value") or "Adventurer").strip() or "Adventurer"
        # prepare attribute rolling
        # Clear to hide the free input field and reset like CLI
        self._emit_clear()
        self.s.phase = "create_attrs"
        self.s.assignments = {}
        self.s.pending_attrs = [
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ]
        self.s.pending_roll = roll_damage(self._get_stat_roll_dice())
        # Show selected difficulty
        difficulty_name = self.DIFFICULTY_CONFIG[self.s.difficulty]["name"]
        difficulty_dice = self.DIFFICULTY_CONFIG[self.s.difficulty]["dice"]
        self._emit_dialogue(
            f"Difficulty: {difficulty_name} ({difficulty_dice} stat rolls)"
        )
        self._emit_dialogue("")
        # Intro and first roll lines via dialogues
        try:
            self._emit_dialogue(
                get_dialogue("system", "attribute_roll_intro", None, None)
                or "Rolling your attributes..."
            )
        except Exception:
            self._emit_dialogue("Rolling your attributes...")
        try:
            self._emit_dialogue(
                (
                    get_dialogue("system", "attribute_roll", None, None)
                    or "Rolling for attribute {i} of {total}..."
                ).format(i=1, total=7)
            )
        except Exception:
            self._emit_dialogue("Rolling for attribute 1 of 7...")
        try:
            self._emit_dialogue(
                (
                    get_dialogue("system", "you_rolled", None, None)
                    or "You rolled a {roll}!"
                ).format(roll=self.s.pending_roll)
            )
        except Exception:
            self._emit_dialogue(f"You rolled a {self.s.pending_roll}!")
        self._emit_dialogue(
            get_dialogue("system", "choose_attribute", None, None)
            or "Choose which attribute to assign this value to:"
        )
        self._emit_menu(
            [(f"attr:{i}", attr) for i, attr in enumerate(self.s.pending_attrs)]
        )
        self._emit_state()
        # Temporarily stash the future character name in subphase
        self.s.subphase = name
        return self._flush()

    def _handle_create_attrs(self, action: str) -> List[Event]:
        # Handle staged continues in creation flow
        if action == "create:attrs_continue":
            # Proceed to HP/Gold narration after attributes are finalized
            name = self.s.subphase or "Adventurer"
            con = self.s.assignments.get("Constitution", 10)
            self._emit_clear()
            # HP calc narration
            self._emit_dialogue(
                get_dialogue("system", "calc_hp_gold", None, None)
                or "Calculating your starting HP and Gold..."
            )
            try:
                self._emit_dialogue(
                    (
                        get_dialogue("system", "your_constitution", None, None)
                        or "Your Constitution is {con}..."
                    ).format(con=con)
                )
            except Exception:
                self._emit_dialogue(f"Your Constitution is {con}...")
            self._emit_dialogue(
                get_dialogue("system", "rolling_hp_bonus", None, None)
                or "Rolling 5d4 for HP bonus..."
            )
            base_hp = 3 * con
            hp_bonus = roll_damage("5d4")
            hp = base_hp + hp_bonus
            try:
                self._emit_dialogue(
                    (
                        get_dialogue("system", "hp_result", None, None)
                        or "Base HP: {base} + Bonus: {bonus} = {hp} HP!"
                    ).format(base=base_hp, bonus=hp_bonus, hp=hp)
                )
            except Exception:
                self._emit_dialogue(
                    f"Base HP: {base_hp} + Bonus: {hp_bonus} = {hp} HP!"
                )
            # Gold calc narration (new formula)
            self._emit_dialogue(
                get_dialogue("system", "rolling_gold", None, None)
                or "Rolling 20d6 for starting gold..."
            )
            base_gold = roll_damage("20d6")
            cha = int(self.s.assignments.get("Charisma", 10))
            # Charisma bonus: ceil(CHA / 1.5) d6
            try:
                cha_dice = int(math.ceil(cha / 1.5))
            except Exception:
                cha_dice = max(0, (cha + 1) // 2)  # safe fallback
            if cha_dice > 0:
                try:
                    self._emit_dialogue(f"Charisma bonus: rolling {cha_dice}d6...")
                except Exception:
                    pass
                cha_bonus = roll_damage(f"{cha_dice}d6")
            else:
                cha_bonus = 0
            # Low HP bonus tiers (apply highest matching)
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

            if hp_bonus_die:
                try:
                    self._emit_dialogue(
                        f"Low-HP bonus: +{hp_bonus_die} (because HP {hp})"
                    )
                except Exception:
                    pass
                low_hp_bonus = roll_damage(hp_bonus_die)
            else:
                low_hp_bonus = 0
            gold = base_gold + cha_bonus + low_hp_bonus
            # Final gold result narration
            try:
                if hp_bonus_die:
                    self._emit_dialogue(
                        (
                            get_dialogue("system", "gold_result_detailed", None, None)
                            or "Base Gold: {base} + CHA Bonus: {cha_b} + Low-HP Bonus: {hp_b} = {gold} Gold!"
                        ).format(
                            base=base_gold,
                            cha_b=cha_bonus,
                            hp_b=low_hp_bonus,
                            gold=gold,
                        )
                    )
                else:
                    self._emit_dialogue(
                        (
                            get_dialogue("system", "gold_result", None, None)
                            or "Base Gold: {base} + CHA Bonus: {cha_b} = {gold} Gold!"
                        ).format(base=base_gold, cha_b=cha_bonus, gold=gold)
                    )
            except Exception:
                msg = (
                    f"Base Gold: {base_gold} + CHA Bonus: {cha_bonus} + Low-HP Bonus: {low_hp_bonus} = {gold} Gold!"
                    if hp_bonus_die
                    else f"Base Gold: {base_gold} + CHA Bonus: {cha_bonus} = {gold} Gold!"
                )
                self._emit_dialogue(msg)
            # Create the character but stay in creation phase for staged summary
            c = Character(name=name, clazz="Adventurer", max_hp=hp, gold=gold)
            c.hp = hp
            c.attributes = self.s.assignments.copy()
            self.s.character = c
            # Gate with Continue to proceed to creation summary
            self._emit_pause()
            self._emit_menu([("create:hp_continue", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "create:hp_continue":
            # Show creation summary (name/hp/gold) then continue to town
            c = self.s.character
            self._emit_clear()
            self._emit_dialogue(
                (
                    get_dialogue("system", "creation_complete", None, c)
                    or "\nCharacter creation complete!"
                )
            )
            name = c.name if c else (self.s.subphase or "Adventurer")
            hp = c.hp if c else 0
            gold = c.gold if c else 0
            # Prefer 'Name' variant explicitly if present
            try:
                d = load_dialogues() or {}
                sysd = d.get("system", {}) if isinstance(d, dict) else {}
                node = (
                    sysd.get("creation_name_line", {}) if isinstance(sysd, dict) else {}
                )
                choices = node.get("dialogues", []) if isinstance(node, dict) else []
                pref = None
                for t in choices or []:
                    if isinstance(t, str) and t.strip().lower().startswith("name"):
                        pref = t
                        break
                if pref:
                    self._emit_dialogue(pref.format(name=name))
                else:
                    # Fallback to dialogue picker or default
                    nl = get_dialogue("system", "creation_name_line", None, c)
                    self._emit_dialogue(nl.format(name=name) if nl else f"Name: {name}")
            except Exception:
                self._emit_dialogue(f"Name: {name}")
            try:
                hl = get_dialogue("system", "creation_hp_line", None, c)
                self._emit_dialogue(hl.format(hp=hp) if hl else f"HP: {hp}")
            except Exception:
                self._emit_dialogue(f"HP: {hp}")
            try:
                gl = get_dialogue("system", "creation_gold_line", None, c)
                self._emit_dialogue(gl.format(gold=gold) if gl else f"Gold: {gold}")
            except Exception:
                self._emit_dialogue(f"Gold: {gold}")
            self._emit_dialogue(
                get_dialogue("system", "starting_note", None, c)
                or "You start with no weapons or armor - visit the shop to equip yourself!. Best of luck adventurer"
            )
            self._emit_pause()
            self._emit_menu([("create:summary_continue", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "create:summary_continue":
            # Enter town: show header, summary and choices
            self._emit_clear()
            # Set town background (new path via scene manager)
            try:
                from .scene_manager import set_town_background

                ev = set_town_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
                else:
                    self._emit_scene("town_menu/town.png")
            except Exception:
                self._emit_scene("town_menu/town.png")
            c = self.s.character
            self.s.phase = "town"
            self._emit_dialogue(
                get_dialogue("system", "town_header", None, c)
                or get_dialogue("combat", "town_header", None, c)
                or "=== Town ==="
            )
            try:
                if c:
                    self._emit_dialogue(c.summary())
            except Exception:
                pass
            self._emit_menu(self._town_choices())
            self._emit_update_stats()
            return self._flush()
        # Always clear before (re)rendering the attribute UI to ensure the screen resets
        if not action.startswith("attr:"):
            # re-show choices; clear like CLI between each assignment
            idx_text = len(self.s.assignments) + 1
            self._emit_clear()
            try:
                self._emit_dialogue(
                    (
                        get_dialogue("system", "attribute_roll", None, None)
                        or "Rolling for attribute {i}..."
                    ).format(i=idx_text, total=7)
                )
            except Exception:
                self._emit_dialogue(f"Rolling for attribute {idx_text} of 7...")
            try:
                self._emit_dialogue(
                    (
                        get_dialogue("system", "you_rolled", None, None)
                        or "You rolled a {roll}!"
                    ).format(roll=self.s.pending_roll)
                )
            except Exception:
                self._emit_dialogue(f"You rolled a {self.s.pending_roll}!")
            self._emit_dialogue(
                get_dialogue("system", "choose_attribute", None, None)
                or "Choose which attribute to assign this value to:"
            )
            self._emit_menu(
                [(f"attr:{i}", attr) for i, attr in enumerate(self.s.pending_attrs)]
            )
            self._emit_state()
            return self._flush()

        i = int(action.split(":", 1)[1])
        if i < 0 or i >= len(self.s.pending_attrs):
            return self._flush()

        attr = self.s.pending_attrs.pop(i)
        roll = int(self.s.pending_roll or 10)
        self.s.assignments[attr] = roll

        if self.s.pending_attrs:
            self.s.pending_roll = roll_damage(self._get_stat_roll_dice())
            count_done = len(self.s.assignments)
            self._emit_clear()
            self._emit_dialogue(f"Assigned {roll} to {attr}!")
            try:
                self._emit_dialogue(
                    (
                        get_dialogue("system", "attribute_roll", None, None)
                        or "Rolling for attribute {i} of {total}..."
                    ).format(i=count_done + 1, total=7)
                )
            except Exception:
                self._emit_dialogue(f"Rolling for attribute {count_done+1} of 7...")
            try:
                self._emit_dialogue(
                    (
                        get_dialogue("system", "you_rolled", None, None)
                        or "You rolled a {roll}!"
                    ).format(roll=self.s.pending_roll)
                )
            except Exception:
                self._emit_dialogue(f"You rolled a {self.s.pending_roll}!")
            self._emit_dialogue(
                get_dialogue("system", "choose_attribute", None, None)
                or "Choose which attribute to assign this value to:"
            )
            self._emit_menu(
                [(f"attr:{i}", a) for i, a in enumerate(self.s.pending_attrs)]
            )
            self._emit_state()
            return self._flush()

        # finalize attributes: stage a recap then continue to HP/Gold narration
        name = self.s.subphase or "Adventurer"
        # Remember last assignment for recap
        self.s.last_assignment = (attr, roll)
        self._emit_clear()
        try:
            recap = (
                get_dialogue("system", "attribute_assigned", None, None)
                or "Assigned {roll} to {attr}!"
            )
            self._emit_dialogue(recap.format(roll=roll, attr=attr))
        except Exception:
            self._emit_dialogue(f"Assigned {roll} to {attr}!")
        # Header before final stats list
        try:
            hdr = (
                get_dialogue("system", "final_stats_header", None, None)
                or "Final stats"
            )
            self._emit_dialogue(hdr)
        except Exception:
            self._emit_dialogue("Final stats")
        # Show full assigned attributes
        order = [
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ]
        for a in order:
            if a in self.s.assignments:
                try:
                    self._emit_dialogue(f"{a}: {self.s.assignments[a]}")
                except Exception:
                    pass
        # Gate with Continue before HP/Gold narration
        self._emit_pause()
        self._emit_menu([("create:attrs_continue", "Continue")])
        self._emit_state()
        return self._flush()

    def _handle_town(self, action: str, payload: Dict[str, Any]) -> List[Event]:
        # Generic back to town menu
        if action == "town":
            # reset any subphase like gambling
            self.s.subphase = ""
            self.s.gamble = {}
            self._emit_clear()
            return self._render_town_menu()

        # Weaponsmith sub-actions
        if action.startswith("repair:"):
            return self._weaponsmith_handle(action)
        # Gambling sub-flow handling
        if (self.s.subphase or "").startswith("gamble"):
            # Route both prompt submits and button/menu actions into gambling handler
            if (
                action == "prompt:submit"
                or action.startswith("gamble:")
                or action.startswith("bet:")
                or action.startswith("exact:")
                or action.startswith("range:")
                or action.startswith("guess:")
            ):
                return self._gamble_handle(action, payload)

        # Companion sub-flow handling
        if action.startswith("comp:") or (self.s.subphase or "").startswith(
            "companion"
        ):
            return self._companion_handle(action, payload)

        # Primary town actions
        c = self.s.character
        if action == "town:enter":
            # Reset per-visit flags when venturing into the labyrinth
            if c is not None:
                try:
                    setattr(c, "rest_attempted", False)
                    setattr(c, "used_rest", False)
                    setattr(c, "used_sleep", False)
                    setattr(c, "used_eat", False)
                    setattr(c, "used_tavern", False)
                    setattr(c, "used_pray", False)
                    setattr(c, "prayed", False)
                except Exception:
                    pass
            # If a prior revival requested a depth reset, apply it now just before entering
            try:
                if bool(getattr(self.s, "defer_depth_reset", False)):
                    self.s.depth = 1
                    self.s.room_history = []
                    setattr(self.s, "defer_depth_reset", False)
            except Exception:
                pass
            # Set labyrinth background for dungeon
            self._emit_scene("labyrinth.png")
            # Mark to show gate guard message on first room render
            self.s.subphase = "entering_dng_gate"
            self.s.phase = "dungeon"
            self.s.current_room = None
            return self._enter_room()
        if action == "town:shop":
            self.s.phase = "shop"
            return self._shop_show_categories()
        if action == "town:train":
            # Training background and menu
            try:
                self._emit_scene("town_menu/training.png")
            except Exception:
                pass
            return self._train_menu()
        if action == "town:inventory":
            self.s.phase = "inventory"
            return self._inventory_show()
        if action == "town:gamble":
            return self._gamble_start()
        if action == "town:companion":
            return self._companion_menu()
        if action == "town:repair":
            return self._weaponsmith_menu()
        if action == "town:rest":
            # Once per town visit; 10g; 5d4 + CON > 25 -> heal ceil(maxHP/3)
            self._emit_clear()
            # Inn background
            self._emit_scene("town_menu/inn.png")
            if getattr(c, "used_rest", False) or getattr(c, "rest_attempted", False):
                self._emit_dialogue(
                    get_dialogue("town", "refresh_used", None, c)
                    or "You've already refreshed in town this visit."
                )
            elif c.gold < 10:
                self._emit_dialogue(
                    get_dialogue("system", "not_enough_gold", None, c)
                    or "You don't have enough gold."
                )
                try:
                    self._emit_dialogue(f"You need 10g but have {c.gold}g.")
                except Exception:
                    pass
            else:
                try:
                    setattr(c, "rest_attempted", True)
                    setattr(c, "used_rest", True)
                except Exception:
                    pass
                self._emit_dialogue(
                    get_dialogue("town", "rest_short", None, c) or "You take a rest..."
                )
                c.gold -= 10
                try:
                    self._emit_dialogue("Paid 10g.")
                except Exception:
                    pass
                self._emit_update_stats()
                con = int(getattr(c, "attributes", {}).get("Constitution", 10))
                roll_total = roll_damage("5d4") + con
                try:
                    self._emit_dialogue(f"Rest check: Roll {roll_total} (need >25)")
                except Exception:
                    pass
                if roll_total > 25:
                    import math as _m

                    heal = max(1, _m.ceil(c.max_hp / 3))
                    before = c.hp
                    c.hp = min(c.max_hp, c.hp + heal)
                    actual = c.hp - before
                    msg = get_dialogue("town", "rest_heal", None, c)
                    try:
                        self._emit_dialogue(
                            msg.format(heal=actual)
                            if msg
                            else f"You rest well and heal {actual} HP."
                        )
                    except Exception:
                        self._emit_dialogue(f"You rest well and heal {actual} HP.")
                    self._emit_update_stats()
                else:
                    self._emit_dialogue(
                        get_dialogue("town", "rest_fail", None, c)
                        or "You fail to get a good rest."
                    )
            # Gate back to town
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:healer":
            # Full heal, cleanse debuffs, cost 40g
            self._emit_clear()
            # Healer background
            self._emit_scene("town_menu/healer.png")
            if c.gold < 40:
                self._emit_dialogue(
                    get_dialogue("system", "not_enough_gold", None, c)
                    or get_dialogue("town", "healer_elwen", "no_gold", c)
                    or "You don't have enough gold."
                )
                try:
                    self._emit_dialogue(f"You need 40g but have {c.gold}g.")
                except Exception:
                    pass
            else:
                from .data_loader import get_npc_dialogue

                self._emit_dialogue(
                    get_npc_dialogue("town", "healer_elwen", None, c)
                    or "Sister Elwen: The townsfolk heal your wounds and cleanse harmful effects."
                )
                # heal and cleanse
                c.hp = c.max_hp
                try:
                    for k in list(getattr(c, "persistent_buffs", {}).keys()):
                        if k.startswith("debuff_"):
                            c.persistent_buffs.pop(k, None)
                except Exception:
                    pass
                c.gold -= 40
                try:
                    self._emit_dialogue("Paid 40g.")
                except Exception:
                    pass
                self._emit_update_stats()
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:eat":
            self._emit_clear()
            # Eat background
            self._emit_scene("town_menu/eat.png")
            if getattr(c, "used_eat", False):
                self._emit_dialogue(
                    get_dialogue("town", "refresh_used", None, c)
                    or "You've already refreshed in town this visit."
                )
                self._emit_pause()
                self._emit_menu([("town", "Continue")])
                self._emit_state()
                return self._flush()
            if c.gold < 10:
                self._emit_dialogue(
                    get_dialogue("town", "cook_hera", "no_gold", c)
                    or "You can't afford a meal."
                )
                try:
                    self._emit_dialogue(f"You need 10g but have {c.gold}g.")
                except Exception:
                    pass
            else:
                from .data_loader import get_npc_dialogue

                cook = get_npc_dialogue("town", "cook_hera", None, c)
                cook_name = cook.split(":", 1)[0] if cook else "Hera"
                meal = (
                    get_dialogue("town", "eat_meal", None, c)
                    or "You eat a hearty meal and feel better."
                )
                self._emit_dialogue(f"{cook_name}: {meal}")
                c.gold -= 10
                try:
                    self._emit_dialogue("Paid 10g.")
                except Exception:
                    pass
                # CHA-based check: 5d4 + CHA > 25 => heal ceil(maxHP/3)
                try:
                    cha = int(getattr(c, "attributes", {}).get("Charisma", 10))
                except Exception:
                    cha = 10
                roll_total = roll_damage("5d4") + cha
                try:
                    self._emit_dialogue(f"{cook_name}: Roll {roll_total} (need >25)")
                except Exception:
                    pass
                if roll_total > 25:
                    import math as _m

                    heal = max(1, _m.ceil(c.max_hp / 3))
                    before = c.hp
                    c.hp = min(c.max_hp, c.hp + heal)
                    actual = c.hp - before
                    try:
                        self._emit_dialogue(f"{cook_name}: You recover {actual} HP.")
                    except Exception:
                        pass
                    self._emit_update_stats()
                else:
                    line = (
                        get_dialogue("town", "eat_fail", None, c)
                        or "Despite the meal, you don't feel much better."
                    )
                    try:
                        self._emit_dialogue(f"{cook_name}: {line}")
                    except Exception:
                        self._emit_dialogue(line)
                try:
                    setattr(c, "used_eat", True)
                except Exception:
                    pass
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:tavern":
            self._emit_clear()
            # Tavern background
            self._emit_scene("town_menu/tavern.png")
            if getattr(c, "used_tavern", False):
                self._emit_dialogue(
                    get_dialogue("town", "refresh_used", None, c)
                    or "You've already refreshed in town this visit."
                )
                self._emit_pause()
                self._emit_menu([("town", "Continue")])
                self._emit_state()
                return self._flush()
            if c.gold < 10:
                self._emit_dialogue(
                    get_dialogue("town", "bartender_roth", "no_gold", c)
                    or "You can't afford a drink."
                )
                try:
                    self._emit_dialogue(f"You need 10g but have {c.gold}g.")
                except Exception:
                    pass
            else:
                from .data_loader import get_npc_dialogue

                bark = get_npc_dialogue("town", "bartender_roth", None, c)
                bark_name = bark.split(":", 1)[0] if bark else "Roth"
                # CHA-based check: 5d4 + CHA > 25 => heal ceil(maxHP/3)
                try:
                    cha = int(getattr(c, "attributes", {}).get("Charisma", 10))
                except Exception:
                    cha = 10
                roll_total = roll_damage("5d4") + cha
                try:
                    self._emit_dialogue(f"{bark_name}: Roll {roll_total} (need >25)")
                except Exception:
                    pass
                if roll_total > 25:
                    import math as _m

                    heal = max(1, _m.ceil(c.max_hp / 3))
                    before = c.hp
                    c.hp = min(c.max_hp, c.hp + heal)
                    actual = c.hp - before
                    msg = (
                        get_dialogue("town", "drink_heal", None, c)
                        or "The drink soothes you — {heal} HP restored."
                    )
                    try:
                        msg = msg.format(heal=actual)
                    except Exception:
                        msg = f"The drink refreshes you for {actual} HP."
                    self._emit_dialogue(f"{bark_name}: {msg}")
                    self._emit_update_stats()
                else:
                    talk = (
                        get_dialogue("town", "drink_talk", None, c)
                        or "You hear some tavern chatter."
                    )
                    self._emit_dialogue(f"{bark_name}: {talk}")
                c.gold -= 10
                try:
                    self._emit_dialogue("Paid 10g.")
                except Exception:
                    pass
                self._emit_update_stats()
                try:
                    setattr(c, "used_tavern", True)
                except Exception:
                    pass
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:pray":
            self._emit_clear()
            # Temple background
            self._emit_scene("town_menu/temple.png")
            if getattr(c, "used_pray", False):
                self._emit_dialogue(
                    get_dialogue("town", "refresh_used", None, c)
                    or "You've already refreshed in town this visit."
                )
            else:
                from .data_loader import get_npc_dialogue

                prefix = get_npc_dialogue("town", "priestess_eira", None, c)
                name = prefix.split(":", 1)[0] if prefix else "Eira"
                self._emit_dialogue(prefix or "You kneel and offer a prayer.")
                wis = int(getattr(c, "attributes", {}).get("Wisdom", 10))
                roll_total = roll_damage("5d4") + wis
                try:
                    self._emit_dialogue(f"{name}: Roll {roll_total} (need >25)")
                except Exception:
                    pass
                if roll_total > 25:
                    import math as _m

                    heal = max(1, _m.ceil(c.max_hp / 3))
                    before = c.hp
                    c.hp = min(c.max_hp, c.hp + heal)
                    actual = c.hp - before
                    line = get_dialogue("town", "praying_heal", None, c)
                    try:
                        text = (
                            line or "You feel comforted and heal {heal} HP."
                        ).format(heal=actual)
                    except Exception:
                        text = f"You feel comforted and heal {actual} HP."
                    self._emit_dialogue(f"{name}: {text}")
                    self._emit_update_stats()
                else:
                    line = (
                        get_dialogue("town", "praying_fail", None, c)
                        or "Your faith isn't strong enough."
                    )
                    self._emit_dialogue(f"{name}: {line}")
                try:
                    setattr(c, "prayed", True)
                    setattr(c, "used_pray", True)
                except Exception:
                    pass
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:sleep":
            # Once per town visit; 5d4 + CON > 25 -> heal ceil(maxHP/3)
            # Show inn background while resting
            try:
                self._emit_scene("town_menu/inn.png")
            except Exception:
                pass
            if getattr(c, "used_sleep", False):
                self._emit_dialogue(
                    get_dialogue("town", "refresh_used", None, c)
                    or "You've already refreshed in town this visit."
                )
            else:
                con = int(getattr(c, "attributes", {}).get("Constitution", 10))
                roll_total = roll_damage("5d4") + con
                try:
                    self._emit_dialogue(
                        f"You settle in to sleep... Roll {roll_total} (need >25)"
                    )
                except Exception:
                    pass
                if roll_total > 25:
                    import math as _m

                    heal = max(1, _m.ceil(c.max_hp / 3))
                    before = c.hp
                    c.hp = min(c.max_hp, c.hp + heal)
                    actual = c.hp - before
                    self._emit_dialogue(
                        get_dialogue("town", "sleep_success", None, c)
                        or "You sleep soundly and feel reinvigorated."
                    )
                    try:
                        self._emit_dialogue(f"You recover {actual} HP.")
                    except Exception:
                        pass
                    self._emit_update_stats()
                else:
                    self._emit_dialogue(
                        get_dialogue("town", "sleep_fail", None, c)
                        or "You toss and turn and gain little rest."
                    )
                try:
                    setattr(c, "used_sleep", True)
                except Exception:
                    pass
            # Gate back to town
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:quests":
            return self._quests_menu()
        if action == "quests:continue":
            return self._quests_menu()
        if action == "quests:new":
            # Ask town for new quests and re-render menu
            c = self.s.character
            try:
                current = list(getattr(c, "side_quests", []) or [])
            except Exception:
                current = []
            if len(current) >= 3:
                # Show capacity message when already at 3
                self._emit_dialogue(
                    get_dialogue("town", "too_many_quests", None, c)
                    or "You already have three side quests."
                )
                self._emit_pause()
                self._emit_menu([("quests:continue", "Continue")])
                self._emit_state()
                return self._flush()
            try:
                from .quests import quest_manager

                quest_manager.ask_for_new_quests(self.s.character, n=3)
            except Exception:
                pass
            self._emit_dialogue(
                get_dialogue("town", "new_quests_posted", None, c)
                or "New side quest offers have been posted."
            )
            self._emit_pause()
            self._emit_menu([("quests:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:level":
            return self._level_menu()
        # Level allocation selection
        if action.startswith("level:"):
            return self._level_handle(action)
        if action == "town:sleep":
            # Handled earlier (sleep flow); keep this for safety but route to town
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "town:remove_curses":
            # Healer background (curse removal)
            self._emit_scene("town_menu/healer.png")
            return self._remove_curses_menu()
        if action == "town:save":
            self._emit_dialogue(
                get_dialogue("system", "save_not_implemented", None, c)
                or "Save is not implemented in the web version yet."
            )
            return self._render_town_menu()
        # Handle training attribute selection
        if action.startswith("train:"):
            return self._train_handle(action)
        if action == "town:quit":
            self.s.phase = "main_menu"
            return self.start()

        # Default: re-show town menu
        return self._render_town_menu()

    def _render_town_menu(self) -> List[Event]:
        # Centralized town menu rendering: header + character summary + menu.
        # Set town background
        try:
            from .scene_manager import set_town_background

            ev = set_town_background()
            bg = ev.get("data", {}).get("background") if isinstance(ev, dict) else None
            if bg:
                self._emit_scene(bg)
            else:
                self._emit_scene("town_menu/town.png")
        except Exception:
            self._emit_scene("town_menu/town.png")
        c = self.s.character
        self._emit_dialogue(
            get_dialogue("system", "town_header", None, c)
            or get_dialogue("combat", "town_header", None, c)
            or "=== Town ==="
        )
        try:
            if c:
                self._emit_dialogue(c.summary())
        except Exception:
            pass
        self._emit_menu(self._town_choices())
        self._emit_state()
        return self._flush()

    def _enter_room(self) -> List[Event]:
        # Generate a fresh room if needed
        if self.s.current_room is None:
            # Trap check before room generation (like CLI)
            trap = random_room_trap()
            if trap and self.s.character:
                lines = resolve_trap_events(self.s.character, trap)
                for ln in lines:
                    self._emit_dialogue(ln)
                self._emit_update_stats()
                if self.s.character.hp <= 0:
                    # If a trap kills you outside of combat, use the same revival flow
                    # as combat deaths so you respawn in town (with deferred depth reset)
                    try:
                        return self._attempt_revival({"name": "Trap"})
                    except Exception:
                        # Fallback: go to main menu
                        self._emit_dialogue(
                            get_dialogue("system", "death", None, self.s.character)
                            or "You have died! Game Over!"
                        )
                        self.s.phase = "main_menu"
                        self._emit_menu(
                            [
                                ("main:new", "New Game"),
                                ("main:load", "Load Game"),
                                ("main:quit", "Quit"),
                            ]
                        )
                        self._emit_state()
                        return self._flush()
            room = generate_room(self.s.depth, self.s.character)

            # Override monster for special conditions:
            # - 50th monster encountered across the run
            # If the upcoming encounter would be the 50th, force Dragon.
            try:
                upcoming = int(getattr(self.s, "monster_encounters", 0)) + 1
            except Exception:
                upcoming = 1
            if room.monster and upcoming == 50:
                try:
                    from .labyrinth import _monster_by_name

                    forced = _monster_by_name("Dragon", self.s.depth)
                    if forced:
                        room.monster = forced
                except Exception:
                    pass

            # Apply a forced monster from a previously committed preview, if present
            try:
                forced_name = getattr(self.s, "next_forced_monster", None)
                if forced_name:
                    from .labyrinth import _monster_by_name as _MBN2

                    forced_mon = _MBN2(str(forced_name), self.s.depth)
                    if forced_mon:
                        room.monster = forced_mon
                # Clear forced marker after use
                setattr(self.s, "next_forced_monster", None)
            except Exception:
                pass

            # Defer room background scene emission until after we clear the UI below

            self.s.current_room = {
                "description": room.description,
                "gold_reward": room.gold_reward,
                "has_chest": room.has_chest,
                "chest_gold": getattr(room, "chest_gold", 0),
                "chest_magic_item": getattr(room, "chest_magic_item", None),
                "room_id": getattr(room, "room_id", None),
                "monster": (
                    None
                    if not room.monster
                    else {
                        "name": room.monster.name,
                        "hp": room.monster.hp,
                        "armor_class": room.monster.armor_class,
                        "damage_die": room.monster.damage_die,
                        "gold_reward": room.monster.gold_reward,
                        "strength": room.monster.strength,
                        "dexterity": room.monster.dexterity,
                    }
                ),
            }

        room = self.s.current_room
        # Precompute next-room preview (monster only) so Divine/Listen agree and match reality
        try:
            target_depth = int(self.s.depth) + 1
            current_preview = getattr(self.s, "peek_next", None)
            if not (
                isinstance(current_preview, dict)
                and current_preview.get("depth") == target_depth
            ):
                nxt = generate_room(target_depth, self.s.character)
                # Emulate 50th encounter forcing in preview for consistency
                try:
                    upcoming_now = int(getattr(self.s, "monster_encounters", 0))
                    if room.get("monster"):
                        upcoming_now += 1
                    upcoming_next = upcoming_now + 1
                    if getattr(nxt, "monster", None) and upcoming_next == 50:
                        from .labyrinth import _monster_by_name as _MBN

                        forced = _MBN("Dragon", target_depth)
                        if forced:
                            nxt.monster = forced
                except Exception:
                    pass
                mname = getattr(getattr(nxt, "monster", None), "name", None)
                self.s.peek_next = {"depth": target_depth, "monster": mname or None}
        except Exception:
            pass
        # Clear like CLI at each room view BEFORE setting the room background
        self._emit_clear()
        # Always ensure the room background is set when (re)entering a room,
        # even if the room was already generated (e.g., after combat victory)
        try:
            from .scene_manager import set_room_background

            ev = set_room_background(room.get("description", ""))
            bg = ev.get("data", {}).get("background") if isinstance(ev, dict) else None
            if bg:
                self._emit_scene(bg)
        except Exception:
            pass
        # After background is set, render text
        # If just entering from town, show gate guard line once
        try:
            if self.s.subphase == "entering_dng_gate":
                from .data_loader import get_npc_dialogue

                gg = get_npc_dialogue("town", "gate_guard", None, self.s.character)
                if gg:
                    # Ensure the guard line includes a name prefix for consistency
                    if ":" in gg:
                        self._emit_dialogue(gg)
                    else:
                        self._emit_dialogue(f"Gate Guard Garrick: {gg}")
                self.s.subphase = ""
        except Exception:
            self.s.subphase = ""
        # Ambient room intro line from dialogues when available
        ambient = get_dialogue("labyrinth", "room_entry", None, self.s.character)
        header = f"=== Labyrinth Depth {self.s.depth} ===\n\n{self.s.character.summary()}\n\n{room['description']}"
        if ambient:
            self._emit_dialogue(f"{header}\n\n{ambient}")
        else:
            self._emit_dialogue(header)
        if room.get("monster"):
            # Special dramatic intro for Dragon
            m = room["monster"]
            self.s.monster_encounters = (
                int(getattr(self.s, "monster_encounters", 0)) + 1
            )
            if (m.get("name") or "").lower() == "dragon":
                try:
                    line = get_dialogue(
                        "system", "dragon_appears", None, self.s.character
                    )
                except Exception:
                    line = None
                if line:
                    self._emit_dialogue(line)
                else:
                    self._emit_dialogue(
                        "A thunderous wingbeat shakes the cavern. The Dragon emerges from the dark!"
                    )
            else:
                self._emit_dialogue(f"A {m['name']} appears!")
            # Enter combat but gate initiative behind an explicit Continue
            self.s.phase = "combat"
            self.s.subphase = "pause_after_spawn"
            self._emit_pause()
            self._emit_menu([("combat:after_spawn", "Continue")])
            self._emit_state()
            return self._flush()
        else:
            # Pause after viewing the room when it's empty, then show navigation
            self._emit_pause()
            menu: List[Tuple[str, str]] = [("dng:deeper", "1) Go deeper")]
            if (self.s.depth > 1) or (self.s.room_history):
                menu.append(("dng:back", "2) Go back"))
            else:
                menu.append(("dng:town", "2) Return to town"))
            menu.append(("dng:divine", "3) Ask for divine assistance"))
            menu.append(("dng:listen", "4) Listen at the door"))
            menu.append(("dng:open_chest", "5) Open a chest"))
            menu.append(("dng:examine_items", "6) Examine magic item"))
            menu.append(("dng:use_potion", "7) Use a healing potion"))
            self._emit_menu(menu)
        self._emit_state()
        return self._flush()

    def _handle_dungeon(self, action: str) -> List[Event]:
        if action == "dng:deeper":
            # push current depth for backtracking
            try:
                self.s.room_history.append(self.s.depth)
            except Exception:
                self.s.room_history = [self.s.depth]
            # Reset once-per-depth utilities when leaving this depth
            try:
                setattr(self.s, "used_divine_depth", None)
                setattr(self.s, "used_listen_depth", None)
            except Exception:
                pass
            # Consume precomputed preview so the next room's monster matches the hints
            try:
                forced_name = None
                pv = getattr(self.s, "peek_next", None)
                if isinstance(pv, dict) and pv.get("depth") == (self.s.depth + 1):
                    forced_name = pv.get("monster")
                setattr(self.s, "next_forced_monster", forced_name)
                # Clear preview; will be recomputed upon entering the new room
                self.s.peek_next = None
            except Exception:
                try:
                    setattr(self.s, "next_forced_monster", None)
                except Exception:
                    pass
            # Enforce maximum depth of 5
            if self.s.depth >= 5:
                # Already at final depth; just refresh current room
                self.s.depth = 5
                self.s.current_room = None
                return self._enter_room()
            self.s.depth += 1
            self.s.current_room = None
            return self._enter_room()
        elif action == "dng:town":
            self.s.phase = "town"
            # Reset rest attempt when returning to town
            if self.s.character is not None:
                try:
                    setattr(self.s.character, "rest_attempted", False)
                    setattr(self.s.character, "used_rest", False)
                    setattr(self.s.character, "used_sleep", False)
                    setattr(self.s.character, "used_eat", False)
                    setattr(self.s.character, "used_tavern", False)
                    setattr(self.s.character, "used_pray", False)
                    setattr(self.s.character, "prayed", False)
                except Exception:
                    pass
            # Reset once-per-depth utilities when leaving the dungeon
            try:
                setattr(self.s, "used_divine_depth", None)
                setattr(self.s, "used_listen_depth", None)
            except Exception:
                pass
            self._emit_clear()
            # Set town background when returning from dungeon
            try:
                from .scene_manager import set_town_background

                ev = set_town_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
                else:
                    self._emit_scene("town_menu/town.png")
            except Exception:
                self._emit_scene("town_menu/town.png")
            self._emit_dialogue(
                get_dialogue("system", "town_header", None, self.s.character)
                or get_dialogue("combat", "town_header", None, self.s.character)
                or "=== Town ==="
            )
            try:
                if self.s.character:
                    self._emit_dialogue(self.s.character.summary())
            except Exception:
                pass
            self._emit_menu(self._town_choices())
            self._emit_state()
            return self._flush()
        elif action == "dng:back":
            # Step back towards town according to history or depth
            # Reset once-per-depth utilities when leaving this depth
            try:
                setattr(self.s, "used_divine_depth", None)
                setattr(self.s, "used_listen_depth", None)
            except Exception:
                pass
            if self.s.room_history:
                self.s.depth = max(1, int(self.s.room_history.pop()))
            else:
                if self.s.depth > 1:
                    self.s.depth -= 1
                else:
                    # At depth 1, going back returns to town
                    self.s.phase = "town"
                    self._emit_clear()
                    # Set town background when returning from dungeon
                    try:
                        from .scene_manager import set_town_background

                        ev = set_town_background()
                        bg = (
                            ev.get("data", {}).get("background")
                            if isinstance(ev, dict)
                            else None
                        )
                        if bg:
                            self._emit_scene(bg)
                        else:
                            self._emit_scene("town_menu/town.png")
                    except Exception:
                        self._emit_scene("town_menu/town.png")
                    return self._render_town_menu()
            self.s.current_room = None
            return self._enter_room()
        elif action == "dng:result_continue":
            # Generic continue after room utility result screens
            return self._enter_room()
        elif action == "dng:divine":
            c = self.s.character
            # Enforce once-per-depth usage
            try:
                if getattr(self.s, "used_divine_depth", None) == self.s.depth:
                    self._emit_dialogue(
                        "You've already asked for divine assistance at this depth."
                    )
                    self._emit_pause()
                    self._emit_menu([("dng:result_continue", "Continue")])
                    self._emit_state()
                    return self._flush()
            except Exception:
                pass
            # New mechanics: 5d4 + Wisdom must be > 25
            wis = getattr(c, "attributes", {}).get("Wisdom", 10)
            base = roll_damage("5d4")
            r = base + wis
            line = get_dialogue("combat", "divine_attempt", None, c)
            msg = (
                line.format(roll=r)
                if line
                else f"You pray for guidance... Roll {base} + WIS {wis} = {r} (need >25)"
            )
            try:
                self._emit_dialogue(msg)
            except Exception:
                self._emit_dialogue(
                    f"You pray for guidance... Roll {base} + WIS {wis} = {r} (need >25)"
                )
            if r > 25:
                # Use precomputed preview for consistency
                pv = getattr(self.s, "peek_next", None)
                mname = None
                if isinstance(pv, dict) and pv.get("depth") == (self.s.depth + 1):
                    mname = pv.get("monster")
                else:
                    # Fallback: compute one now (and store it)
                    try:
                        nxt = generate_room(self.s.depth + 1, c)
                        mname = getattr(getattr(nxt, "monster", None), "name", None)
                        self.s.peek_next = {"depth": self.s.depth + 1, "monster": mname}
                    except Exception:
                        mname = None
                if mname:
                    v = get_dialogue("system", "vision_monster", None, c)
                    try:
                        self._emit_dialogue(
                            v.format(name=mname)
                            if v
                            else f"A vision shows a {mname} ahead."
                        )
                    except Exception:
                        self._emit_dialogue(f"A vision shows a {mname} ahead.")
                else:
                    self._emit_dialogue(
                        get_dialogue("system", "vision_empty", None, c)
                        or "A vision shows an empty corridor ahead."
                    )
            else:
                self._emit_dialogue(
                    get_dialogue("system", "no_vision", None, c) or "No vision comes."
                )
            # Mark used for this depth
            try:
                setattr(self.s, "used_divine_depth", self.s.depth)
            except Exception:
                pass
            # Gate with Continue instead of refreshing immediately
            self._emit_pause()
            self._emit_menu([("dng:result_continue", "Continue")])
            self._emit_state()
            return self._flush()
        elif action == "dng:listen":
            # Dedicated listen result screen
            # Enforce once-per-depth usage
            try:
                if getattr(self.s, "used_listen_depth", None) == self.s.depth:
                    self._emit_dialogue("You've already listened at this depth.")
                    self._emit_pause()
                    self._emit_menu([("dng:result_continue", "Continue")])
                    self._emit_state()
                    return self._flush()
            except Exception:
                pass
            self._emit_clear()
            c = self.s.character
            per = getattr(c, "attributes", {}).get("Perception", 10)
            # New mechanics: 5d4 + Perception must be > 25
            base = roll_damage("5d4")
            total = base + per
            listen = get_dialogue("system", "listen_roll", None, c)
            msg = (
                listen.format(roll=total)
                if listen
                else f"You listen carefully... Roll {base} + PER {per} = {total} (need >25)"
            )
            try:
                self._emit_dialogue(msg)
            except Exception:
                self._emit_dialogue(
                    f"You listen carefully... Roll {base} + PER {per} = {total} (need >25)"
                )
            if total > 25:
                from .data_loader import load_monster_sounds

                mapping = {
                    (s.get("name", "") or "").lower(): s.get("sound", "Unknown")
                    for s in (load_monster_sounds() or [])
                }
                # Use the preview for consistency with Divine and the actual next room
                pv = getattr(self.s, "peek_next", None)
                pname = None
                if isinstance(pv, dict) and pv.get("depth") == (self.s.depth + 1):
                    pname = pv.get("monster")
                else:
                    try:
                        nxt = generate_room(self.s.depth + 1, c)
                        pname = getattr(getattr(nxt, "monster", None), "name", None)
                        self.s.peek_next = {"depth": self.s.depth + 1, "monster": pname}
                    except Exception:
                        pname = None
                if pname:
                    name = (pname or "").lower()
                    hint = mapping.get(name, "Unknown")
                    line = get_dialogue("system", "you_hear", None, c)
                    try:
                        self._emit_dialogue(
                            line.format(hint=hint) if line else f"You hear: {hint}."
                        )
                    except Exception:
                        self._emit_dialogue(f"You hear: {hint}.")
                else:
                    self._emit_dialogue(
                        get_dialogue("system", "sounds_quiet", None, c)
                        or "It sounds quiet ahead."
                    )
            else:
                self._emit_dialogue(
                    get_dialogue("system", "hear_nothing", None, c)
                    or "You hear nothing useful."
                )
            # Mark used for this depth
            try:
                setattr(self.s, "used_listen_depth", self.s.depth)
            except Exception:
                pass
            # Gate with Continue instead of refreshing immediately
            self._emit_pause()
            self._emit_menu([("dng:result_continue", "Continue")])
            self._emit_state()
            return self._flush()
        elif action == "dng:open_chest":
            # Dedicated chest result screen
            self._emit_clear()
            c = self.s.character
            room = self.s.current_room or {}
            if not room.get("has_chest"):
                self._emit_dialogue(
                    get_dialogue("system", "no_chest", None, c)
                    or "There is no chest in this room."
                )
                self._emit_pause()
                self._emit_menu([("dng:result_continue", "Continue")])
                self._emit_state()
                return self._flush()
            gold = int(room.get("chest_gold", 0))
            if gold:
                c.gold += gold
                try:
                    line = get_dialogue("system", "open_chest_gold", None, c)
                    self._emit_dialogue(
                        line.format(gold=gold)
                        if line
                        else f"You open the chest and find {gold} gold!"
                    )
                except Exception:
                    self._emit_dialogue(f"You open the chest and find {gold} gold!")
            item_name = room.get("chest_magic_item")
            if item_name:
                line = get_dialogue("system", "find_magic_item", None, c)
                try:
                    self._emit_dialogue(
                        line.format(item=item_name)
                        if line
                        else f"You also find a {item_name}!"
                    )
                except Exception:
                    self._emit_dialogue(f"You also find a {item_name}!")
                # Add as a simple named item entry on the character for now
                try:
                    from .entities import MagicItem

                    c.magic_items.append(
                        MagicItem(
                            name=item_name,
                            type="trinket",
                            effect="",
                            bonus=0,
                            penalty=0,
                            description="An unknown artifact.",
                        )
                    )
                except Exception:
                    pass
            # Mark chest as opened
            self.s.current_room["has_chest"] = False
            self.s.current_room["chest_gold"] = 0
            self.s.current_room["chest_magic_item"] = None
            self._emit_update_stats()
            # Gate with Continue instead of refreshing immediately
            self._emit_pause()
            self._emit_menu([("dng:result_continue", "Continue")])
            self._emit_state()
            return self._flush()
        elif action == "dng:use_potion":
            c = self.s.character
            if not c:
                return self._enter_room()

            # Check if any potions available
            if c.potions <= 0 and not c.potion_uses:
                self._emit_dialogue("You don't have any potions.")
                self._emit_pause()
                self._emit_menu([("dng:result_continue", "Continue")])
                self._emit_state()
                return self._flush()

            # Show potion selection menu
            options = []
            idx = 1
            if c.potions > 0:
                options.append(
                    ("dng_pot:legacy", f"{idx}) Healing (legacy) ({c.potions} uses)")
                )
                idx += 1
            for name, uses in c.potion_uses.items():
                if uses > 0:
                    options.append((f"dng_pot:{name}", f"{idx}) {name} ({uses} uses)"))
                    idx += 1
            options.append(("dng:result_continue", f"{idx}) Back"))

            self._emit_dialogue("Choose a potion to use:")
            self._emit_menu(options)
            self._emit_state()
            return self._flush()
        elif action.startswith("dng_pot:"):
            c = self.s.character
            if not c:
                return self._enter_room()

            potion_name = action.split(":", 1)[1]

            if potion_name == "legacy":
                if c.potions > 0:
                    con = c.attributes.get("Constitution", 10)
                    mult = max(1, math.ceil(con / 2))
                    heal = 0
                    for _ in range(mult):
                        heal += max(1, roll_damage("2d2"))
                    c.hp = min(c.max_hp, c.hp + heal)
                    c.potions -= 1
                    self._emit_dialogue(
                        f"You drink a healing potion and recover {heal} HP."
                    )
                    self._emit_update_stats()
            else:
                # Handle named potions
                lname = potion_name.lower()
                uses = c.potion_uses.get(potion_name, 0)
                if uses > 0:
                    if lname == "healing":
                        con = c.attributes.get("Constitution", 10)
                        mult = max(1, math.ceil(con / 2))
                        heal = 0
                        for _ in range(mult):
                            heal += max(1, roll_damage("2d2"))
                        c.hp = min(c.max_hp, c.hp + heal)
                        c.potion_uses[potion_name] -= 1
                        if c.potion_uses[potion_name] <= 0:
                            del c.potion_uses[potion_name]
                        self._emit_dialogue(
                            f"You drink a healing potion and recover {heal} HP."
                        )
                        self._emit_update_stats()
                    elif lname == "antidote":
                        c.potion_uses[potion_name] -= 1
                        if c.potion_uses[potion_name] <= 0:
                            del c.potion_uses[potion_name]
                        c.persistent_buffs.pop("debuff_poison", None)
                        self._emit_dialogue(
                            "You drink the antidote and feel the poison leave your system."
                        )
                        self._emit_update_stats()
                    else:
                        self._emit_dialogue("This potion can only be used in combat.")

            self._emit_pause()
            self._emit_menu([("dng:result_continue", "Continue")])
            self._emit_state()
            return self._flush()
        elif action == "dng:examine_items":
            c = self.s.character
            if not getattr(c, "magic_items", None):
                self._emit_dialogue(
                    get_dialogue("system", "no_magic_items", None, c)
                    or "You have no magic items to examine."
                )
                self._emit_pause()
                self._emit_menu([("dng:result_continue", "Continue")])
                self._emit_state()
                return self._flush()
            self._emit_dialogue(
                get_dialogue("system", "magic_items_list", None, c)
                or "Magic items in your possession:"
            )
            try:
                for i, item in enumerate(c.magic_items, 1):
                    name = getattr(item, "name", str(item))
                    self._emit_dialogue(f"{i}) {name}")
            except Exception:
                pass
            # Gate with Continue instead of refreshing immediately
            self._emit_pause()
            self._emit_menu([("dng:result_continue", "Continue")])
            self._emit_state()
            return self._flush()
        else:
            # Refresh room view
            return self._enter_room()

    def _handle_combat(self, action: str) -> List[Event]:
        # Event-driven combat loop
        import sys

        if self.debug:
            print(f"[DEBUG] _handle_combat called with action={action}")
            sys.stdout.flush()
            print(f"[DEBUG] phase={self.s.phase}, subphase={self.s.subphase}")
            sys.stdout.flush()
            print(f"[DEBUG] current_room={self.s.current_room is not None}")
            sys.stdout.flush()

        # CRITICAL: Handle revival subphases BEFORE checking for monster
        # because _attempt_revival clears current_room
        sp = self.s.subphase or "player_menu"

        # Revival handlers (these must come first, before monster check)
        if sp == "revival_success" and action == "combat:revival_success_continue":
            if self.debug:
                print(f"[DEBUG] Revival handler triggered! sp={sp}, action={action}")
                sys.stdout.flush()
                print(
                    f"[DEBUG] Before changes - phase={self.s.phase}, current_room={self.s.current_room}"
                )
                sys.stdout.flush()

            # IMPORTANT: Set phase to town FIRST before clearing room state
            # This prevents re-entry bugs where cleared room triggers dungeon routing
            self.s.phase = "town"
            self.s.subphase = ""
            if self.debug:
                print(f"[DEBUG] Phase set to town, subphase cleared")
                sys.stdout.flush()

            # Now clear combat/room state to ensure no dungeon remnants
            try:
                self.s.current_room = None
                self.s.room_history = []
                self.s.combat = {}
                if self.debug:
                    print(f"[DEBUG] Cleared room/combat state")
                    sys.stdout.flush()
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] Error clearing state: {e}")
                    sys.stdout.flush()

            self._emit_clear()
            if self.debug:
                print(f"[DEBUG] Emitted clear")
                sys.stdout.flush()

            # Force scene reset by sending null, then town background
            self._emit_scene(None)
            if self.debug:
                print(f"[DEBUG] Emitted null scene")
                sys.stdout.flush()

            try:
                from .scene_manager import set_town_background

                ev = set_town_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
                    if self.debug:
                        print(f"[DEBUG] Emitted town background: {bg}")
                        sys.stdout.flush()
                else:
                    self._emit_scene("town_menu/town.png")
                    if self.debug:
                        print(f"[DEBUG] Emitted fallback town background")
                        sys.stdout.flush()
            except Exception as e:
                self._emit_scene("town_menu/town.png")
                if self.debug:
                    print(f"[DEBUG] Exception in background, used fallback: {e}")
                    sys.stdout.flush()

            if self.debug:
                print(f"[DEBUG] About to call _render_town_menu()")
                sys.stdout.flush()
                print(
                    f"[DEBUG] Final state - phase={self.s.phase}, current_room={self.s.current_room}"
                )
                sys.stdout.flush()
            return self._render_town_menu()

        if sp == "revival_fail" and action == "combat:revival_fail_continue":
            # Proceed to main menu after permanent death page
            try:
                self.s.depth = 1
            except Exception:
                pass
            # Reset once-per-depth utilities on death
            try:
                setattr(self.s, "used_divine_depth", None)
                setattr(self.s, "used_listen_depth", None)
            except Exception:
                pass
            self.s.phase = "main_menu"
            # Clear first, then force background reset by sending null, then labyrinth
            self._emit_clear()
            # Emit a blank scene to force reset the background state on client
            self._emit_scene(None)
            # Now emit labyrinth - client will see it as a change from None
            self._emit_scene("labyrinth.png")
            self._emit_menu(
                [
                    ("main:new", "New Game"),
                    ("main:load", "Load Game"),
                    ("main:quit", "Quit"),
                ]
            )
            self._emit_state()
            return self._flush()

        # NOW check for monster (after revival handlers)
        room = self.s.current_room or {}
        mon = room.get("monster")
        if not mon:
            if self.debug:
                print(f"[DEBUG] No monster found, routing to dungeon")
                sys.stdout.flush()
            self.s.phase = "dungeon"
            return self._enter_room()

        # First entry: initialize combat state
        if self.s.subphase == "start" and action == "combat:fight":
            return self._combat_begin(mon)

        # Route by remaining subphases
        if self.debug:
            print(f"[DEBUG] Routing by subphase: sp={sp}")
        # Pause-gated continues for spawn/initiative/victory
        if sp == "pause_after_spawn" and action == "combat:after_spawn":
            self.s.subphase = "initiative"
            return self._combat_roll_initiative()
        if sp == "post_initiative" and action == "combat:after_initiative":
            self.s.subphase = (
                "player_menu"
                if self.s.combat.get("turn") == "player"
                else "monster_defend"
            )
            return self._combat_emit_menu()
        if sp == "victory_pending" and action == "combat:victory_pending_continue":
            # Now render the full victory summary page
            room = self.s.current_room or {}
            mon = room.get("monster") or {}
            return self._combat_victory(room, mon)
        if sp == "victory_continue" and action == "combat:victory_continue":
            # After showing victory summary and pause, return to the same room view
            self.s.phase = "dungeon"
            return self._enter_room()
        # Action result continue routes
        if sp == "examine_continue" and action == "combat:after_examine":
            self.s.subphase = "monster_defend"
            return self._combat_emit_menu()
        if sp == "charm_continue" and action == "combat:after_charm":
            self.s.subphase = "monster_defend"
            return self._combat_emit_menu()
        if sp == "charm_success" and action == "combat:charm_success_continue":
            # After successful charm and rewards, return to the room view
            self.s.phase = "dungeon"
            return self._enter_room()
        if sp == "run_success" and action == "combat:run_success_continue":
            # Leave combat and go to town after confirming
            self.s.phase = "town"
            self._emit_clear()
            try:
                from .scene_manager import set_town_background

                ev = set_town_background()
                bg = (
                    ev.get("data", {}).get("background")
                    if isinstance(ev, dict)
                    else None
                )
                if bg:
                    self._emit_scene(bg)
                else:
                    self._emit_scene("town_menu/town.png")
            except Exception:
                self._emit_scene("town_menu/town.png")
            return self._render_town_menu()
        if sp == "run_fail" and action == "combat:run_fail_continue":
            self.s.subphase = "monster_defend"
            return self._combat_emit_menu()
        if sp == "dragon_victory" and action == "combat:dragon_victory_continue":
            # Winning the game: go to main menu with a short epilogue
            self.s.phase = "main_menu"
            self._emit_clear()
            try:
                ep = get_dialogue("system", "dragon_epilogue", None, self.s.character)
            except Exception:
                ep = None
            if ep:
                self._emit_dialogue(ep)
            else:
                self._emit_dialogue(
                    "You have conquered the Labyrinth. Peace returns to the realm."
                )
            self._emit_menu(
                [
                    ("main:new", "New Game"),
                    ("main:load", "Load Game"),
                    ("main:quit", "Quit"),
                ]
            )
            self._emit_state()
            return self._flush()
        if sp == "initiative":
            return self._combat_roll_initiative()
        if sp == "player_menu":
            return self._combat_player_menu(action)
        if sp == "attack_aim":
            return self._combat_attack_choose_aim(action)
        if sp == "attack_weapon":
            return self._combat_attack_choose_weapon(action)
        if sp == "monster_defend":
            return self._combat_monster_defend_choose(action)
        if sp == "use_potion":
            return self._combat_use_potion(action)
        if sp == "cast_spell":
            return self._combat_cast_spell(action)
        if sp == "lightning_mode":
            return self._combat_cast_lightning_mode(action)
        if sp == "divine":
            return self._combat_divine(action)
        if sp == "charm":
            return self._combat_charm(action)
        if sp == "run":
            return self._combat_run(action)
        if sp == "examine":
            return self._combat_examine(action)

        # Default: show current menu
        return self._combat_emit_menu()

    # ---- Combat helpers ----
    def _combat_begin(self, mon: Dict[str, Any]) -> List[Event]:
        # Initialize
        self.s.combat = {"buffs": {}, "enemy": {"debuffs": {}}, "turn": None}
        # Intro taunt/appearance
        self._emit_combat_update(f"A {mon['name']} appears!")
        # If a monster taunt line exists in dialogues, show it as monster speech
        try:
            c = self.s.character
            taunt = get_dialogue("combat", "monster_taunt", None, c)
            if taunt:
                self._emit_combat_update(self._format_monster_speech(mon, taunt))
        except Exception:
            pass
        # Pause before rolling initiative so spawn appears on its own page
        self.s.subphase = "pause_after_spawn"
        self._emit_pause()
        self._emit_menu([("combat:after_spawn", "Continue")])
        self._emit_state()
        return self._flush()

    def _combat_roll_initiative(self) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        if not c or not mon:
            self.s.phase = "dungeon"
            return self._enter_room()
        # Set monster background as combat begins after spawn continue
        try:
            from .scene_manager import set_monster_background

            ev = set_monster_background(mon.get("name"))
            bg = ev.get("data", {}).get("background") if isinstance(ev, dict) else None
            if bg:
                self._emit_scene(bg)
        except Exception:
            pass
        cdx = c.attributes.get("Dexterity", 10)
        mdx = mon.get("dexterity", 10)
        c_roll = roll_damage("5d4") + cdx
        m_roll = roll_damage("5d4") + mdx
        try:
            mname = str(mon.get("name", "Monster"))
        except Exception:
            mname = "Monster"
        self._emit_combat_update(
            f"Initiative - You: {c_roll} (roll + {cdx}) vs {mname}: {m_roll} (roll + {mdx})"
        )
        # Decide who goes first and immediately show the next options inline
        player_first = c_roll >= m_roll
        self.s.combat["turn"] = "player" if player_first else "monster"
        if player_first:
            self._emit_combat_update("You win initiative and act first.")
            self.s.subphase = "player_menu"
        else:
            self._emit_combat_update(f"{mname} wins initiative and acts first.")
            self.s.subphase = "monster_defend"
        return self._combat_emit_menu()

    def _combat_emit_menu(self) -> List[Event]:
        # Do not clear here; the UI clears on action clicks so prior combat
        # messages (initiative, results) remain visible before choices.
        if self.s.subphase == "player_menu":
            # Build menu - disable examine if already used this combat
            examine_used = self.s.combat.get("actions_used", {}).get("examine", False)
            menu = [
                ("p:attack", "1) Attack"),
                ("p:potion", "2) Drink Potion"),
                ("p:spell", "3) Cast Spell"),
                ("p:divine", "4) Divine Aid"),
                ("p:charm", "5) Charm Monster"),
                ("p:run", "6) Run Away"),
            ]
            if not examine_used:
                menu.append(("p:examine", "7) Examine Monster"))
            else:
                menu.append(("p:examine_disabled", "7) Examine Monster (already used)"))
            self._emit_menu(menu)
            self._emit_state()
        elif self.s.subphase == "monster_defend":
            self._emit_combat_update("Prepare your guard before the attack lands.")
            self._emit_menu(
                [
                    ("defend:high", "1) Head/Upper"),
                    ("defend:middle", "2) Torso/Middle"),
                    ("defend:low", "3) Legs/Lower"),
                ]
            )
            self._emit_state()
        return self._flush()

    def _combat_player_menu(self, action: str) -> List[Event]:
        if action == "p:attack":
            self.s.subphase = "attack_aim"
            # Provide a prompt line so users see guidance, not only buttons
            self._emit_combat_update("Choose where to aim your attack.")
            self._emit_menu(
                [
                    ("aim:high", "1) Head/Upper"),
                    ("aim:middle", "2) Torso/Middle"),
                    ("aim:low", "3) Legs/Lower"),
                ]
            )
            self._emit_state()
            return self._flush()
        if action == "p:potion":
            self.s.subphase = "use_potion"
            return self._combat_use_potion(None)
        if action == "p:spell":
            self.s.subphase = "cast_spell"
            return self._combat_cast_spell(None)
        if action == "p:divine":
            self.s.subphase = "divine"
            return self._combat_divine(None)
        if action == "p:charm":
            self.s.subphase = "charm"
            return self._combat_charm(None)
        if action == "p:run":
            self.s.subphase = "run"
            return self._combat_run(None)
        if action == "p:examine":
            # Check if already used this combat
            if self.s.combat.get("actions_used", {}).get("examine", False):
                self._emit_combat_update("You've already examined this creature.")
                return self._combat_emit_menu()
            self.s.subphase = "examine"
            return self._combat_examine(None)
        if action == "p:examine_disabled":
            self._emit_combat_update("You've already examined this creature.")
            return self._combat_emit_menu()
        return self._combat_emit_menu()

    def _combat_attack_choose_aim(self, action: str) -> List[Event]:
        if not action.startswith("aim:"):
            return self._combat_emit_menu()
        zone = action.split(":", 1)[1]
        self.s.combat["aim"] = zone
        c = self.s.character
        if c and len(c.weapons) > 1:
            self.s.subphase = "attack_weapon"
            self._emit_combat_update("Choose your weapon.")
            menu = [
                (
                    f"weapon:{i}",
                    f"{i+1}) {w.name} ({getattr(w,'damage_die','1d4')})",
                )
                for i, w in enumerate(c.weapons)
            ]
            self._emit_menu(menu)
            self._emit_state()
            return self._flush()
        widx = (
            c.equipped_weapon_index
            if (c and 0 <= c.equipped_weapon_index < len(c.weapons))
            else 0
        )
        return self._combat_attack_resolve(widx)

    def _combat_attack_choose_weapon(self, action: str) -> List[Event]:
        if not action.startswith("weapon:"):
            return self._combat_emit_menu()
        try:
            idx = int(action.split(":", 1)[1])
        except Exception:
            idx = 0
        return self._combat_attack_resolve(idx)

    def _combat_attack_resolve(self, weapon_index: int) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        if not c or not mon:
            self.s.phase = "dungeon"
            return self._enter_room()
        zone = self.s.combat.get("aim", "middle")
        monster_defend_zone = random.choice(["high", "middle", "low"])
        weapon = None
        if c.weapons and 0 <= weapon_index < len(c.weapons):
            weapon = c.weapons[weapon_index]
        enemy_ac = max(
            1,
            mon.get("armor_class", 10)
            - self.s.combat.get("enemy", {}).get("debuffs", {}).get("ac_penalty", 0),
        )
        attack_die = roll_damage("5d4")
        str_mod = c.attributes.get("Strength", 10)
        attack_roll = attack_die + str_mod
        self._emit_combat_update(
            f"You aim {zone} and roll: {attack_die} + Strength({str_mod}) = {attack_roll} vs AC {enemy_ac}"
        )
        self._emit_combat_update(
            f"The {mon['name']} braces to defend {monster_defend_zone}."
        )
        # Fumble on minimum roll (5 for 5d4): player injures self
        if attack_die == 5:
            self_dmg = max(1, roll_damage("1d4"))
            c.hp -= self_dmg
            self._emit_combat_update(
                f"Massive fail! You injure yourself for {self_dmg} HP. Your HP: {max(c.hp, 0)}"
            )
            self._emit_update_stats()
            if c.hp <= 0:
                return self._combat_player_defeated(mon)
            return self._combat_next_turn("monster")
        # Natural 20 crit
        if attack_die == 20:
            # Unarmed does fixed 2 damage, weapons roll their damage die
            if weapon:
                dmg_die = getattr(weapon, "damage_die", "1d2")
                base_dmg = roll_damage(dmg_die)
            else:
                base_dmg = 2  # Fixed unarmed damage

            base_dmg += math.ceil(str_mod / 2) + self.s.combat.get("buffs", {}).get(
                "damage_bonus", 0
            )
            if weapon and getattr(weapon, "damaged", False):
                base_dmg = max(1, base_dmg // 2)
            dmg = max(1, base_dmg)
            crit = int(dmg * 1.5)
            mon["hp"] -= crit
            try:
                mname = str(mon.get("name", "Monster"))
            except Exception:
                mname = "Monster"
            self._emit_combat_update(
                f"Critical hit! You deal {crit} damage. {mname} HP: {max(mon['hp'], 0)}"
            )
            if mon["hp"] <= 0:
                # Gate victory so the attack text is visible before summary screen
                self.s.subphase = "victory_pending"
                self._emit_pause()
                self._emit_menu([("combat:victory_pending_continue", "Continue")])
                self._emit_state()
                return self._flush()
            self._emit_update_stats()
            return self._combat_next_turn("monster")
        # Perfect defense
        if monster_defend_zone == zone:
            self._emit_combat_update(
                f"Your attack is blocked by the {monster_defend_zone} guard!"
            )
            return self._combat_next_turn("monster")
        # Normal resolve
        if attack_roll >= enemy_ac:
            # Unarmed does fixed 2 damage, weapons roll their damage die
            if weapon:
                dmg_die = getattr(weapon, "damage_die", "1d2")
                base_dmg = roll_damage(dmg_die)
            else:
                base_dmg = 2  # Fixed unarmed damage

            base_dmg += math.ceil(str_mod / 2) + self.s.combat.get("buffs", {}).get(
                "damage_bonus", 0
            )
            if weapon and getattr(weapon, "damaged", False):
                base_dmg = max(1, base_dmg // 2)
            dmg = max(1, base_dmg)
            mon["hp"] -= dmg
            try:
                mname = str(mon.get("name", "Monster"))
            except Exception:
                mname = "Monster"
            self._emit_combat_update(
                f"Hit! You deal {dmg} damage. {mname} HP: {max(mon['hp'], 0)}"
            )
            # Chance to damage player's weapon on successful hit (0.1% per monster AC)
            try:
                mc = int(mon.get("armor_class", 10))
                chance = mc * 0.001
                if random.random() < chance and weapon:
                    setattr(weapon, "damaged", True)
                    self._emit_combat_update(
                        f"Unlucky! Your {weapon.name} is damaged and now less effective."
                    )
            except Exception:
                pass
            # Monster hurt reaction flavor line, when available
            try:
                from .data_loader import get_npc_dialogue

                hurt = get_npc_dialogue("monster", "hurt_reaction", None, mon)
                if hurt:
                    # Use standardized monster speech formatter to ensure name prefix
                    self._emit_combat_update(self._format_monster_speech(mon, hurt))
            except Exception:
                pass
            if mon["hp"] <= 0:
                # Gate victory so the attack text (and flavor) is visible first
                self.s.subphase = "victory_pending"
                self._emit_pause()
                self._emit_menu([("combat:victory_pending_continue", "Continue")])
                self._emit_state()
                return self._flush()
        else:
            self._emit_combat_update("You miss!")
            # Even blocked/missed attacks can sometimes damage weapons on perfect defense
            try:
                if monster_defend_zone == zone and weapon:
                    mc = int(mon.get("armor_class", 10))
                    chance = mc * 0.001
                    if random.random() < chance:
                        setattr(weapon, "damaged", True)
                        self._emit_combat_update(
                            f"Unlucky! Your {weapon.name} is damaged and now less effective."
                        )
            except Exception:
                pass
        self._emit_update_stats()
        return self._combat_next_turn("monster")

    def _combat_next_turn(self, turn: str) -> List[Event]:
        room = self.s.current_room or {}
        mon = room.get("monster")
        c = self.s.character
        if turn == "monster":
            # Companion acts after player
            try:
                comp = getattr(c, "companion", None)
                if comp and comp.hp > 0 and mon and mon["hp"] > 0:
                    damage_roll = max(
                        1, roll_damage(getattr(comp, "damage_die", "2d6"))
                    )
                    attack_value = random.randint(1, 20) + getattr(comp, "strength", 0)
                    if attack_value > mon.get("armor_class", 10):
                        mon["hp"] -= damage_roll
                        # Use dialogue-based hit message when available
                        from .data_loader import get_dialogue

                        hit_line = get_dialogue("companion", "attack_hit", None, c)
                        if hit_line:
                            try:
                                self._emit_combat_update(
                                    hit_line.format(
                                        comp=comp.name,
                                        dmg=damage_roll,
                                        hp=max(mon["hp"], 0),
                                    )
                                )
                            except Exception:
                                self._emit_combat_update(
                                    f"{comp.name} attacks for {damage_roll} damage. {mon.get('name','Monster')} HP: {max(mon['hp'], 0)}"
                                )
                        else:
                            self._emit_combat_update(
                                f"{comp.name} attacks for {damage_roll} damage. {mon.get('name','Monster')} HP: {max(mon['hp'], 0)}"
                            )
                        if mon["hp"] <= 0:
                            # Gate victory after companion kill as well
                            self.s.subphase = "victory_pending"
                            self._emit_pause()
                            self._emit_menu(
                                [("combat:victory_pending_continue", "Continue")]
                            )
                            self._emit_state()
                            return self._flush()
                    else:
                        from .data_loader import get_dialogue

                        miss_line = get_dialogue("companion", "attack_miss", None, c)
                        self._emit_combat_update(
                            miss_line.format(comp=comp.name)
                            if miss_line
                            else f"{comp.name} misses."
                        )
            except Exception:
                pass
            self.s.subphase = "monster_defend"
            return self._combat_emit_menu()
        else:
            self.s.subphase = "player_menu"
            return self._combat_emit_menu()

    def _combat_monster_defend_choose(self, action: str) -> List[Event]:
        if not action or not action.startswith("defend:"):
            return self._combat_emit_menu()
        zone = action.split(":", 1)[1]
        self.s.combat["defend"] = zone
        return self._combat_monster_attack_resolve()

    def _combat_monster_attack_resolve(self) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        if not c or not mon:
            self.s.phase = "dungeon"
            return self._enter_room()
        ed = self.s.combat.get("enemy", {}).get("debuffs", {})
        buffs = self.s.combat.get("buffs", {})
        # Freeze skip
        if ed.get("freeze_turns", 0) > 0:
            ed["freeze_turns"] = ed.get("freeze_turns", 0) - 1
            self._emit_combat_update("The monster is frozen and cannot act!")
            return self._combat_next_turn("player")
        if buffs.get("invisibility_charges", 0) > 0:
            buffs["invisibility_charges"] = buffs.get("invisibility_charges", 0) - 1
            self._emit_combat_update("The monster swings wildly but hits nothing!")
            return self._combat_next_turn("player")
        monster_zone = random.choice(["high", "middle", "low"])
        player_defend_zone = self.s.combat.get("defend", "middle")
        self._emit_combat_update(f"You brace to defend {player_defend_zone}.")
        ac = compute_armor_class(c, buffs.get("ac_bonus", 0))
        attack_die = roll_damage("5d4")
        monster_strength = mon.get("strength", 10)
        strength_bonus = monster_strength // 2
        attack_roll = attack_die + strength_bonus
        self._emit_combat_update(
            f"{mon['name']} attacks {monster_zone}: roll {attack_die} + Strength/2({strength_bonus}) = {attack_roll} vs AC {ac}"
        )
        # Fumble on minimum roll (5 for 5d4): monster injures itself
        if attack_die == 5:
            self_dmg = max(
                1,
                roll_damage(mon.get("damage_die", "1d6")) - ed.get("damage_penalty", 0),
            )
            mon["hp"] -= self_dmg
            self._emit_combat_update(
                f"{mon['name']} blunders and injures itself for {self_dmg} HP!"
            )
            if mon["hp"] <= 0:
                return self._combat_victory(room, mon)
            self._emit_update_stats()
            return self._combat_next_turn("player")
        if attack_die == 20:
            dmg = max(
                1,
                roll_damage(mon.get("damage_die", "1d6")) - ed.get("damage_penalty", 0),
            )
            crit = int(dmg * 1.5)
            c.hp -= crit
            self._emit_combat_update(
                f"Critical hit! You take {crit} damage. Your HP: {max(c.hp, 0)}"
            )
            if c.hp <= 0:
                return self._combat_player_defeated(mon)
            self._emit_update_stats()
            return self._combat_next_turn("player")
        if player_defend_zone == monster_zone:
            self._emit_combat_update(
                f"You successfully defend against the {monster_zone} attack!"
            )
            # Blocked attacks still can damage armor per new rules
            try:
                ms = int(mon.get("strength", 10))
                chance = ms * 0.001
                if random.random() < chance and c.armor:
                    setattr(c.armor, "damaged", True)
                    self._emit_combat_update(
                        f"Ouch! Your {c.armor.name} is damaged and provides reduced protection."
                    )
            except Exception:
                pass
            return self._combat_next_turn("player")
        if attack_roll >= ac:
            dmg = max(
                1,
                roll_damage(mon.get("damage_die", "1d6")) - ed.get("damage_penalty", 0),
            )
            c.hp -= dmg
            self._emit_combat_update(
                f"You are hit for {dmg} damage. Your HP: {max(c.hp, 0)}"
            )
            # Chance to damage player's armor on successful monster hit (0.1% per monster strength)
            try:
                ms = int(mon.get("strength", 10))
                chance = ms * 0.001
                if random.random() < chance and c.armor:
                    setattr(c.armor, "damaged", True)
                    self._emit_combat_update(
                        f"Ouch! Your {c.armor.name} is damaged and provides reduced protection."
                    )
            except Exception:
                pass
            if c.hp <= 0:
                return self._combat_player_defeated(mon)
        else:
            self._emit_combat_update(f"{mon['name']} misses!")
        self._emit_update_stats()
        return self._combat_next_turn("player")

    def _combat_player_defeated(self, mon: Dict[str, Any]) -> List[Event]:
        # Use dialogue-driven death message when available
        c = self.s.character
        defeat_line = get_dialogue("combat", "defeated_by", None, c)
        if defeat_line:
            try:
                self._emit_combat_update(self._format_monster_speech(mon, defeat_line))
            except Exception:
                self._emit_combat_update(defeat_line)
        else:
            self._emit_combat_update(f"The {mon['name']} defeats you.")
        # Attempt revival using updated wisdom-based mechanics (5d4 + WIS vs scaling DC)
        return self._attempt_revival(mon)

    def _attempt_revival(self, mon: Dict[str, Any]) -> List[Event]:
        """Attempt to revive the character.

        Mechanics:
        - Increment death_count
        - Wisdom roll = 5d4 + Wisdom
        - Difficulty = 15 + 5 * death_count
        - If success: reduce all attributes by 2 (min 3), set HP=1, return to town
        - If fail: permanent death -> back to main menu
        """
        c = self.s.character
        # Reset text for a dedicated revival screen with a death background, then increment death count
        self._emit_clear()
        try:
            from .scene_manager import set_death_background

            ev = set_death_background()
            bg = ev.get("data", {}).get("background") if isinstance(ev, dict) else None
            if bg:
                self._emit_scene(bg)
            else:
                self._emit_scene("death.png")
        except Exception:
            self._emit_scene("death.png")
        # Ensure subsequent Continue actions are handled by the combat handler
        # (trap deaths may invoke this from dungeon phase)
        try:
            self.s.phase = "combat"
        except Exception:
            pass
        # Increment death count safely
        try:
            setattr(c, "death_count", int(getattr(c, "death_count", 0)) + 1)
        except Exception:
            pass
        death_count = int(getattr(c, "death_count", 1))

        wis = int(getattr(c, "attributes", {}).get("Wisdom", 10))
        rollv = roll_damage("5d4") + wis
        dc = 15 + 5 * death_count

        # Announce attempt (keep text style consistent; leverage dialogues when present)
        try:
            self._emit_combat_update(f"=== DEATH #{death_count} ===")
        except Exception:
            pass
        self._emit_combat_update(
            get_dialogue("combat", "death", None, c)
            or get_dialogue("system", "death", None, c)
            or "You have fallen in battle..."
        )
        self._emit_combat_update(f"Revival attempt: {rollv} (5d4 + WIS {wis}) vs {dc}")

        if rollv >= dc:
            # Success: apply penalties and show a gated Continue screen before routing to Town
            msg = get_dialogue("combat", "revival_success", None, c)
            if msg:
                try:
                    # Provide a simple method description for formatting if needed
                    try:
                        wis_val = int(getattr(c, "attributes", {}).get("Wisdom", 10))
                    except Exception:
                        wis_val = 10
                    if wis_val >= 16:
                        method = "unyielding will"
                    elif wis_val >= 12:
                        method = "iron resolve"
                    else:
                        method = "sheer luck"
                    self._emit_combat_update(msg.format(method=method))
                except Exception:
                    self._emit_combat_update("MIRACULOUS REVIVAL!")
            else:
                self._emit_combat_update("MIRACULOUS REVIVAL!")
            # Apply -1 to all core stats (min 3)
            for attr_name in [
                "Strength",
                "Dexterity",
                "Constitution",
                "Intelligence",
                "Wisdom",
                "Charisma",
                "Perception",
            ]:
                try:
                    old_val = int(getattr(c, "attributes", {}).get(attr_name, 10))
                    new_val = max(3, old_val - 1)
                    c.attributes[attr_name] = new_val
                except Exception:
                    pass
            c.hp = 1
            # Defer depth reset: mark so that on next labyrinth entry we start from depth 1
            try:
                setattr(self.s, "defer_depth_reset", True)
            except Exception:
                pass
            # Reset once-per-depth utilities as we're returning to town due to death
            try:
                setattr(self.s, "used_divine_depth", None)
                setattr(self.s, "used_listen_depth", None)
            except Exception:
                pass
            # Clear any lingering combat/room so re-entering the Labyrinth does not reuse the same monster/room
            try:
                self.s.current_room = None
            except Exception:
                pass
            try:
                self.s.room_history = []
            except Exception:
                pass
            try:
                self.s.combat = {}
            except Exception:
                pass
            # Stay on death screen and gate routing behind Continue
            self._emit_update_stats()
            self.s.subphase = "revival_success"
            self._emit_pause()
            self._emit_menu([("combat:revival_success_continue", "Continue")])
            self._emit_state()
            return self._flush()
        else:
            # Permanent death: show a gated Continue screen before routing to Main Menu
            death_msg = get_dialogue("combat", "permanent_death", None, c)
            if death_msg:
                try:
                    self._emit_combat_update(death_msg)
                except Exception:
                    self._emit_combat_update("PERMANENT DEATH")
            else:
                self._emit_combat_update("PERMANENT DEATH")
            self.s.subphase = "revival_fail"
            self._emit_pause()
            self._emit_menu([("combat:revival_fail_continue", "Continue")])
            self._emit_state()
            return self._flush()

    def _combat_victory(self, room: Dict[str, Any], mon: Dict[str, Any]) -> List[Event]:
        from .data_loader import load_monsters, load_spells, load_magic_items

        # Show victory on a clean page
        self._emit_clear()

        # Depth-scaled XP reward
        monsters = load_monsters()
        entry = next((m for m in monsters if m.get("name") == mon.get("name")), None)
        base_xp = int(entry.get("xp", 10)) if entry else 10
        depth = max(1, int(getattr(self.s, "depth", 1)))
        # Progressive depth multiplier: 1.0, 1.5, 2.0, 2.5, ...
        depth_mult = 1.0 + 0.5 * (depth - 1)
        xp_reward = max(0, int(base_xp * depth_mult))
        msgs = self.s.character.gain_xp(xp_reward)
        self._emit_combat_update(
            f"You defeated the {mon['name']} and gain {xp_reward} XP!"
        )
        try:
            self._emit_combat_update(f"(Depth x{depth_mult:.1f} applied)")
        except Exception:
            pass
        for m in msgs:
            self._emit_combat_update(m)

        # Depth-scaled gold reward based on monsters.json gold_range
        base_gold = None
        try:
            if (
                entry
                and isinstance(entry.get("gold_range"), list)
                and len(entry["gold_range"]) == 2
            ):
                lo, hi = int(entry["gold_range"][0]), int(entry["gold_range"][1])
                if hi < lo:
                    lo, hi = hi, lo
                base_gold = random.randint(lo, hi)
        except Exception:
            base_gold = None
        if base_gold is None:
            try:
                base_gold = int(mon.get("gold_reward", 0))
            except Exception:
                base_gold = 0
        if base_gold is None:
            base_gold = int(room.get("gold_reward", 0))
        gold = max(0, int(base_gold * depth_mult))
        self.s.character.gold += gold
        try:
            self._emit_combat_update(f"You loot {gold} gold! (Depth x{depth_mult:.1f})")
        except Exception:
            self._emit_combat_update(f"You loot {gold} gold!")

        # Side quests progression and auto turn-in for relevant kills
        try:
            from .quests import quest_manager
            from .entities import Monster as _EMonster

            mobj = _EMonster(
                name=mon.get("name", ""),
                hp=int(mon.get("hp", 1)),
                armor_class=int(mon.get("armor_class", 10)),
                damage_die=str(mon.get("damage_die", "1d4")),
            )
            changed = quest_manager.check_kill(self.s.character, mobj)
            if changed:
                for q in changed:
                    try:
                        rw = int(getattr(q, "reward", q.get("reward", 0)))
                    except Exception:
                        rw = 0
                    line = get_dialogue(
                        "town", "quest_turnin_success", None, self.s.character
                    )
                    if line:
                        try:
                            self._emit_combat_update(line.format(reward=rw))
                        except Exception:
                            self._emit_combat_update(
                                f"Quest complete — you receive {rw} gold."
                            )
                    else:
                        self._emit_combat_update(
                            f"Quest complete — you receive {rw} gold."
                        )
        except Exception:
            pass

        # Drops: weight by monster difficulty when available
        diff = int(entry.get("difficulty", 1)) if entry else 1
        potion_chance = min(0.20, 0.05 + diff * 0.01)
        scroll_chance = min(0.20, 0.05 + diff * 0.01)
        item_chance = min(0.12, 0.02 + diff * 0.01)
        rollv = random.random()
        if rollv < potion_chance:
            self.s.character.potions += 1
            self._emit_combat_update("You find a healing potion!")
        elif rollv < potion_chance + scroll_chance:
            spells = load_spells()
            if spells:
                sp = random.choice(spells)
                name = sp.get("name", "Unknown Spell")
                self.s.character.spells[name] = self.s.character.spells.get(name, 0) + 1
                self._emit_combat_update(f"You find a scroll of {name}!")
        elif rollv < potion_chance + scroll_chance + item_chance:
            items = load_magic_items() or []
            if items:
                from .entities import MagicItem

                it = random.choice(items)
                try:
                    mi = MagicItem(
                        name=it.get("name", "Mysterious Item"),
                        type=it.get("type", "misc"),
                        effect=it.get("effect", ""),
                        cursed=bool(it.get("cursed", False)),
                        description=it.get("description", ""),
                        bonus=(
                            int(it.get("bonus", 0))
                            if isinstance(it.get("bonus", 0), int)
                            else 0
                        ),
                        penalty=(
                            int(it.get("penalty", 0))
                            if isinstance(it.get("penalty", 0), int)
                            else 0
                        ),
                        damage_die=it.get("damage_die", ""),
                        bonus_damage=it.get("bonus_damage", ""),
                    )
                except Exception:
                    mi = MagicItem(
                        name=str(it.get("name", "Mysterious Item")),
                        type=str(it.get("type", "misc")),
                        effect=str(it.get("effect", "")),
                    )
                self.s.character.magic_items.append(mi)
                self._emit_combat_update(f"You discover a {mi.name}!")

        room["monster"] = None
        self._emit_update_stats()

        # If this was the Dragon, trigger end-game victory flow
        if (mon.get("name") or "").lower() == "dragon":
            # Clean final victory screen
            self._emit_clear()
            # Victory background
            self._emit_scene("victory.png")
            try:
                line = get_dialogue("system", "dragon_victory", None, self.s.character)
            except Exception:
                line = None
            if line:
                self._emit_dialogue(line)
            else:
                self._emit_dialogue(
                    "With a final roar, the Dragon falls. The labyrinth grows still."
                )
                self._emit_dialogue("Legends will speak of your name for generations.")
            self._emit_pause()
            self.s.subphase = "dragon_victory"
            self._emit_menu([("combat:dragon_victory_continue", "Continue")])
            self._emit_state()
            return self._flush()

        # Pause after victory summary and wait for explicit continue before returning to the room
        self.s.subphase = "victory_continue"
        self._emit_pause()
        self._emit_menu([("combat:victory_continue", "Continue")])
        self._emit_state()
        return self._flush()

    # --- Potions ---
    def _combat_use_potion(self, action: Optional[str]) -> List[Event]:
        c = self.s.character
        buffs = self.s.combat.setdefault("buffs", {})
        if not action:
            options = []
            idx = 1
            if c.potions > 0:
                options.append(("pot:legacy", f"{idx}) Healing (legacy) (1 use)"))
                idx += 1
            for name, uses in c.potion_uses.items():
                if uses > 0:
                    options.append((f"pot:{name}", f"{idx}) {name} ({uses} uses left)"))
                    idx += 1
            if not options:
                self._emit_combat_update("You have no potions.")
                self.s.subphase = "player_menu"
                return self._combat_emit_menu()
            options.append(("pot:back", f"{idx}) Back"))
            self._emit_menu(options)
            self._emit_state()
            return self._flush()
        if action == "pot:back":
            self.s.subphase = "player_menu"
            return self._combat_emit_menu()
        if not action.startswith("pot:"):
            return self._combat_emit_menu()
        name = action.split(":", 1)[1]
        if name == "legacy":
            if c.potions <= 0:
                return self._combat_emit_menu()
            # New formula: ceil(CON/2) * 2d2
            try:
                con = int(getattr(c, "attributes", {}).get("Constitution", 10))
            except Exception:
                con = 10
            mult = max(1, math.ceil(con / 2))
            heal = 0
            for _ in range(mult):
                heal += max(1, roll_damage("2d2"))
            c.hp = min(c.max_hp, c.hp + heal)
            c.potions -= 1
            self._emit_combat_update(
                f"You drink a healing potion and recover {heal} HP."
            )
            self._emit_update_stats()
            return self._combat_next_turn("monster")
        lname = name.lower()
        uses = c.potion_uses.get(name, 0)
        if uses <= 0:
            return self._combat_emit_menu()
        if lname == "healing":
            # New formula: ceil(CON/2) * 2d2
            try:
                con = int(getattr(c, "attributes", {}).get("Constitution", 10))
            except Exception:
                con = 10
            mult = max(1, math.ceil(con / 2))
            heal = 0
            for _ in range(mult):
                heal += max(1, roll_damage("2d2"))
            c.hp = min(c.max_hp, c.hp + heal)
            self._emit_combat_update(
                f"You drink a healing potion and recover {heal} HP."
            )
            c.potion_uses[name] -= 1
            if c.potion_uses[name] <= 0:
                del c.potion_uses[name]
            self._emit_update_stats()
            return self._combat_next_turn("monster")
        if lname == "charisma":
            buffs["cha_bonus"] = buffs.get("cha_bonus", 0) + 2
            c.potion_uses[name] -= 1
            self._emit_combat_update(
                "Your charm glows brighter. (+2 Charisma this combat)"
            )
            return self._combat_next_turn("monster")
        if lname == "intelligence":
            buffs["damage_bonus"] = buffs.get("damage_bonus", 0) + 1
            c.potion_uses[name] -= 1
            self._emit_combat_update("You feel more focused. (+1 damage this combat)")
            return self._combat_next_turn("monster")
        if lname == "speed":
            buffs["extra_attack_charges"] = buffs.get("extra_attack_charges", 0) + 1
            c.potion_uses[name] -= 1
            self._emit_combat_update(
                "Your reflexes quicken. (1 extra attack this combat)"
            )
            return self._combat_next_turn("monster")
        if lname == "strength":
            buffs["damage_bonus"] = buffs.get("damage_bonus", 0) + 2
            c.potion_uses[name] -= 1
            self._emit_combat_update("Your muscles surge. (+2 damage this combat)")
            return self._combat_next_turn("monster")
        if lname == "protection":
            buffs["ac_bonus"] = buffs.get("ac_bonus", 0) + 3
            c.potion_uses[name] -= 1
            self._emit_combat_update(
                "A shimmering barrier surrounds you. (+3 AC this combat)"
            )
            return self._combat_next_turn("monster")
        if lname == "invisibility":
            buffs["invisibility_charges"] = buffs.get("invisibility_charges", 0) + 1
            c.potion_uses[name] -= 1
            self._emit_combat_update(
                "You fade from sight. (Monster's next attack automatically misses)"
            )
            return self._combat_next_turn("monster")
        if lname == "antidote":
            c.potion_uses[name] -= 1
            c.persistent_buffs.pop("debuff_poison", None)
            self._emit_combat_update(
                "You drink the antidote and feel the poison leave your system."
            )
            return self._combat_next_turn("monster")
        self._emit_combat_update("Nothing happens...")
        return self._combat_next_turn("monster")

    # --- Spells ---
    def _combat_cast_spell(self, action: Optional[str]) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        ed = self.s.combat.setdefault("enemy", {}).setdefault("debuffs", {})
        if not action:
            available = [(n, u) for n, u in c.spells.items() if u > 0]
            if not available:
                self._emit_combat_update("You don't know any spells.")
                self.s.subphase = "player_menu"
                return self._combat_emit_menu()
            menu = [
                (f"spell:{name}", f"{i+1}) {name} ({uses} uses left)")
                for i, (name, uses) in enumerate(available)
            ]
            menu.append(("spell:back", f"{len(menu)+1}) Back"))
            self._emit_menu(menu)
            self._emit_state()
            return self._flush()
        if action == "spell:back":
            self.s.subphase = "player_menu"
            return self._combat_emit_menu()
        if not action.startswith("spell:"):
            return self._combat_emit_menu()
        name = action.split(":", 1)[1]
        lname = name.lower()
        if lname == "lightning bolt":
            self.s.subphase = "lightning_mode"
            self.s.combat["spell"] = name
            self._emit_menu(
                [
                    ("lightning:full", "1) Full power"),
                    ("lightning:half", "2) Half power"),
                    ("lightning:back", "3) Back"),
                ]
            )
            self._emit_state()
            return self._flush()
        return self._combat_cast_spell_apply(name, mode=None)

    def _combat_cast_lightning_mode(self, action: Optional[str]) -> List[Event]:
        if action == "lightning:back":
            self.s.subphase = "cast_spell"
            return self._combat_cast_spell(None)
        if action not in ("lightning:full", "lightning:half"):
            return self._combat_emit_menu()
        mode = "full" if action.endswith("full") else "half"
        name = self.s.combat.get("spell")
        return self._combat_cast_spell_apply(name, mode)

    def _combat_cast_spell_apply(self, name: str, mode: Optional[str]) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        ed = self.s.combat.setdefault("enemy", {}).setdefault("debuffs", {})
        if c.spells.get(name, 0) <= 0:
            return self._combat_emit_menu()
        resist = ed.get("spell_resistance", 0)

        def apply_resist(dmg: int) -> int:
            return max(0, dmg - resist)

        lname = name.lower()
        if lname == "summon creature":
            roll = roll_damage("5d4")
            self._emit_combat_update(
                f"You attempt to summon a companion... Roll {roll}"
            )
            # Use the richer table-driven summoning logic from companion.py
            try:
                from .companion import SUMMON_TABLE, create_companion_from_entry
            except Exception:
                SUMMON_TABLE = []
                create_companion_from_entry = None  # type: ignore

            # Compute Int/Cha modifiers (D&D-style)
            int_stat = c.attributes.get("Intelligence", c.attributes.get("Int", 10))
            cha_stat = c.attributes.get("Charisma", c.attributes.get("Cha", 10))
            int_mod = (int_stat - 10) // 2
            cha_mod = (cha_stat - 10) // 2
            final_roll = roll + int_mod + cha_mod

            # Determine eligible entries and choose the best tier, else fail
            eligible = [
                e for e in (SUMMON_TABLE or []) if final_roll >= e.get("min_roll", 999)
            ]
            if eligible and create_companion_from_entry is not None:
                best_min = max(e.get("min_roll", 0) for e in eligible)
                candidates = [e for e in eligible if e.get("min_roll", 0) == best_min]
                import random as _r

                entry = _r.choice(candidates)
                comp = create_companion_from_entry(entry)
                c.companion = comp
                try:
                    self._emit_combat_update(f"A {comp.species} joins you!")
                except Exception:
                    self._emit_combat_update("A companion joins you!")
                c.spells[name] -= 1
                return self._combat_next_turn("monster")
            else:
                self._emit_combat_update(
                    "The summoning fails; no creature answers your call."
                )
                return self._combat_next_turn("monster")
        if lname == "magic missile":
            dmg = apply_resist(max(1, roll_damage("2d6")))
            mon["hp"] -= dmg
            self._emit_combat_update(
                f"Magic missiles strike for {dmg} damage. {mon.get('name','Monster')} HP: {max(mon['hp'], 0)}"
            )
        elif lname == "weakness" or lname == "slowness":
            ed["damage_penalty"] = ed.get("damage_penalty", 0) + 2
            self._emit_combat_update("The foe looks feebler. (-2 damage this combat)")
        elif lname == "lightning bolt":
            die = "6d6" if mode == "full" else "3d6"
            dmg = apply_resist(max(1, roll_damage(die)))
            mon["hp"] -= dmg
            self._emit_combat_update(
                f"Lightning arcs for {dmg} damage. {mon.get('name','Monster')} HP: {max(mon['hp'], 0)}"
            )
        elif lname == "freeze":
            ed["freeze_turns"] = ed.get("freeze_turns", 0) + 1
            self._emit_combat_update("Ice binds the monster. (It skips its next turn)")
        elif lname == "vulnerability":
            ed["ac_penalty"] = ed.get("ac_penalty", 0) + 2
            self._emit_combat_update(
                "Cracks appear in its defenses. (-2 AC this combat)"
            )
        elif lname == "fireball":
            dmg = apply_resist(max(1, roll_damage("4d6")))
            mon["hp"] -= dmg
            self._emit_combat_update(
                f"Fireball explodes for {dmg} damage. {mon.get('name','Monster')} HP: {max(mon['hp'], 0)}"
            )
        elif lname == "heal":
            # Restore HP using a stronger effect than potions
            heal = max(1, roll_damage("8d4"))
            c.hp = min(c.max_hp, c.hp + heal)
            self._emit_combat_update(f"You cast Heal and recover {heal} HP.")
        elif lname == "teleport to town" or lname == "magic portal":
            self._emit_combat_update("A portal whisks you away to town!")
            c.spells[name] -= 1
            self.s.phase = "town"
            self._emit_menu(self._town_choices())
            self._emit_state()
            return self._flush()
        else:
            self._emit_combat_update("The spell fizzles...")
            c.spells[name] -= 1
            return self._combat_next_turn("monster")
        c.spells[name] -= 1
        if mon["hp"] <= 0:
            return self._combat_victory(self.s.current_room, mon)
        self._emit_update_stats()
        return self._combat_next_turn("monster")

    # --- Divine ---
    def _combat_divine(self, action: Optional[str]) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        # Use new mechanics: 5d4 + (Wisdom - 10)
        wis = c.attributes.get("Wisdom", 10)
        base = roll_damage("5d4")
        wis_bonus = wis - 10
        rollv = base + wis_bonus
        self._emit_combat_update(
            f"You call for divine aid... Roll {base} + WIS bonus({wis_bonus}) = {rollv}"
        )
        if rollv >= 12:
            if rollv >= 16:
                die = "4d6"
                name = "Fireball"
            else:
                die = "3d6"
                name = "Lightning Bolt"
            dmg = max(1, roll_damage(die))
            mon["hp"] -= dmg
            self._emit_combat_update(
                f"The gods answer with {name} for {dmg} damage! {mon.get('name','Monster')} HP: {max(mon['hp'], 0)}"
            )
            if mon["hp"] <= 0:
                return self._combat_victory(self.s.current_room, mon)
        else:
            self._emit_combat_update("Your plea goes unanswered.")
        return self._combat_next_turn("monster")

    # --- Charm ---
    def _combat_charm(self, action: Optional[str]) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        # Dedicated charm result screen
        self._emit_clear()
        # Enforce one charm attempt per monster/combat
        used = self.s.combat.setdefault("actions_used", {}).get("charm", False)
        if used:
            self._emit_combat_update(
                "You've already attempted to charm this creature in this fight."
            )
            # Gate next turn behind a Continue and proceed to monster's action
            self.s.subphase = "charm_continue"
            self._emit_pause()
            self._emit_menu([("combat:after_charm", "Continue")])
            self._emit_state()
            return self._flush()
        # Mark as used now (counts even if immune)
        self.s.combat.setdefault("actions_used", {})["charm"] = True
        # Dragons are immune to charm
        try:
            mname = (mon.get("name") or "").lower()
        except Exception:
            mname = ""
        if mname == "dragon":
            self._emit_combat_update("Your charm has no effect on the Dragon!")
            # Gate next turn behind a Continue and proceed to monster's action
            self.s.subphase = "charm_continue"
            self._emit_pause()
            self._emit_menu([("combat:after_charm", "Continue")])
            self._emit_state()
            return self._flush()
        cha = c.attributes.get("Charisma", 10)
        # Include any temporary charisma bonus from buffs (e.g., potion)
        cha_bonus = self.s.combat.get("buffs", {}).get("cha_bonus", 0)
        roll_raw = roll_damage("5d4")
        rollv = roll_raw + cha + cha_bonus
        # Difficulty-based threshold scaling using monsters.json difficulty
        try:
            from .data_loader import load_monsters

            monsters = load_monsters() or []
            entry = next(
                (m for m in monsters if m.get("name") == mon.get("name")),
                None,
            )
            diff = int(entry.get("difficulty", 1)) if entry else 1
        except Exception:
            entry = None
            diff = 1
        threshold = int(28 + math.ceil(1.5 * diff))
        self._emit_combat_update(
            f"You attempt to charm the {mon['name']}... Roll {rollv} ({roll_raw} + CHA({cha}) + bonus({cha_bonus})) (need >{threshold}, diff {diff})"
        )
        if rollv > threshold:
            self._emit_combat_update(
                f"The {mon['name']} is charmed and leaves peacefully."
            )
            # Award reduced rewards on charm: 25% of depth-scaled XP and gold.
            try:
                base_xp = int(entry.get("xp", 10)) if entry else 10
            except Exception:
                base_xp = 10
            depth = max(1, int(getattr(self.s, "depth", 1)))
            depth_mult = 1.0 + 0.5 * (depth - 1)
            xp_reward = max(0, int(base_xp * depth_mult * 0.25))
            # Gold based on monsters.json gold_range, depth-scaled then quartered
            base_gold = None
            try:
                if (
                    entry
                    and isinstance(entry.get("gold_range"), list)
                    and len(entry["gold_range"]) == 2
                ):
                    lo, hi = int(entry["gold_range"][0]), int(entry["gold_range"][1])
                    if hi < lo:
                        lo, hi = hi, lo
                    base_gold = random.randint(lo, hi)
            except Exception:
                base_gold = None
            if base_gold is None:
                try:
                    base_gold = int(mon.get("gold_reward", 0))
                except Exception:
                    base_gold = 0
            if base_gold is None:
                base_gold = int(room.get("gold_reward", 0))
            gold = max(0, int(base_gold * depth_mult * 0.25))
            # Apply rewards (no quests or drops on charm)
            try:
                _ = self.s.character.gain_xp(xp_reward)
            except Exception:
                pass
            try:
                self.s.character.gold += gold
            except Exception:
                pass
            if xp_reward or gold:
                try:
                    self._emit_combat_update(
                        f"Charmed reward: +{xp_reward} XP and +{gold} gold (Depth x{depth_mult:.1f}, Charm 25%, no loot/quests)."
                    )
                except Exception:
                    self._emit_combat_update(
                        f"Charmed reward: +{xp_reward} XP and +{gold} gold (no loot/quests)."
                    )
            self._emit_update_stats()
            room["monster"] = None
            # Stay on a dedicated result screen; route to room after Continue
            self.s.subphase = "charm_success"
            self._emit_pause()
            self._emit_menu([("combat:charm_success_continue", "Continue")])
            self._emit_state()
            return self._flush()
        else:
            self._emit_combat_update("Your charm attempt fails.")
            # Gate next turn behind a Continue
            self.s.subphase = "charm_continue"
            self._emit_pause()
            self._emit_menu([("combat:after_charm", "Continue")])
            self._emit_state()
            return self._flush()

    # --- Run ---
    def _combat_run(self, action: Optional[str]) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        # Dedicated run result screen
        self._emit_clear()
        dex = c.attributes.get("Dexterity", 10)
        # Use rounded-up Dex/2 per new mechanics
        dex_bonus = math.ceil(dex / 2)
        monster_dex = mon.get("dexterity", 10)
        monster_bonus = math.ceil(monster_dex / 2)
        attack_die = roll_damage("5d4")
        rollv = attack_die + dex_bonus
        threshold = 15 + monster_bonus
        self._emit_combat_update(
            f"You attempt to run away... Roll {rollv} ({attack_die} + Dex/2({dex_bonus}) = {rollv}) (need >{threshold})"
        )
        if rollv > threshold:
            self._emit_combat_update("You successfully escape!")
            self.s.subphase = "run_success"
            self._emit_pause()
            self._emit_menu([("combat:run_success_continue", "Continue")])
            self._emit_state()
            return self._flush()
        else:
            self._emit_combat_update("You fail to escape!")
            self.s.subphase = "run_fail"
            self._emit_pause()
            self._emit_menu([("combat:run_fail_continue", "Continue")])
            self._emit_state()
            return self._flush()

    # --- Examine ---
    def _combat_examine(self, action: Optional[str]) -> List[Event]:
        c = self.s.character
        room = self.s.current_room or {}
        mon = room.get("monster")
        # Dedicated examine result screen
        self._emit_clear()
        wis = c.attributes.get("Wisdom", 10)
        rollv = roll_damage("5d4") + wis
        self._emit_combat_update(
            f"You examine the {mon['name']}... (Wisdom check: {rollv})"
        )
        if rollv > 25:
            self._emit_combat_update(
                f"You can see: HP {mon['hp']}, AC {mon['armor_class']}"
            )
            if "dexterity" in mon:
                self._emit_combat_update(f"Dexterity: {mon['dexterity']}")
            # Add a brief monster description from data/monsters_desc.json when available
            try:
                from .data_loader import load_monster_descriptions

                descs = load_monster_descriptions() or {}
                desc = descs.get(mon["name"]) or descs.get(str(mon["name"]).title())
                if desc:
                    self._emit_combat_update(f"It's a {mon['name']} - {desc}")
            except Exception:
                pass
        else:
            self._emit_combat_update(
                "You can't make out the creature's capabilities clearly."
            )
        # Mark that examine has been used this combat
        self.s.combat.setdefault("actions_used", {})["examine"] = True
        # Gate next turn behind a Continue - returns to PLAYER menu (no monster attack)
        self.s.subphase = "examine_continue"
        self._emit_pause()
        self._emit_menu([("combat:after_examine", "Continue")])
        self._emit_state()
        return self._flush()

    # ----- helpers -----
    def _town_choices(self) -> List[Tuple[str, str]]:
        # Labels pulled from dialogues.json with fallbacks to match CLI numbering
        g = lambda key, dflt: get_dialogue("town", key, None, self.s.character) or dflt
        return [
            ("town:enter", g("menu_enter", "1) Enter Labyrinth")),
            ("town:shop", g("menu_shop", "2) Shop")),
            ("town:inventory", g("menu_inventory", "3) Inventory")),
            ("town:rest", g("menu_rest", "4) Inn (10g)")),
            ("town:healer", g("menu_healer", "5) Healer (40g)")),
            ("town:tavern", g("menu_tavern", "6) Tavern (10g)")),
            ("town:eat", g("menu_eat", "7) Eat (10g)")),
            ("town:gamble", g("menu_gamble", "8) Gamble")),
            ("town:pray", g("menu_pray", "9) Temple")),
            ("town:level", g("menu_level", "10) Level Up")),
            ("town:quests", g("menu_quests", "11) Quests")),
            ("town:train", g("menu_train", "12) Train (50g)")),
            ("town:sleep", g("menu_sleep", "13) Sleep")),
            ("town:companion", g("menu_companion", "14) Companion")),
            ("town:repair", g("menu_repair", "15) Repair (30g)")),
            (
                "town:remove_curses",
                g("menu_remove_curses", "16) Remove Curses (10g)"),
            ),
            ("town:save", g("menu_save", "17) Save")),
            ("town:quit", g("menu_quit", "18) Quit")),
        ]

    def _emit_dialogue(self, text: str):
        self.s.buffer.append({"type": "dialogue", "text": text})

    def _emit_menu(self, items: List[Tuple[str, str]]):
        self.s.buffer.append(
            {"type": "menu", "items": [{"id": i, "label": lbl} for i, lbl in items]}
        )

    def _emit_prompt(self, pid: str, label: str):
        self.s.buffer.append({"type": "prompt", "id": pid, "label": label})

    def _emit_state(self):
        self.s.buffer.append({"type": "state", "data": self.snapshot()})

    def _emit_update_stats(self):
        self.s.buffer.append({"type": "update_stats", "data": self.snapshot()})

    def _emit_pause(self):
        self.s.buffer.append({"type": "pause"})

    def _emit_clear(self):
        self.s.buffer.append({"type": "clear"})

    def _emit_combat_update(self, text: str):
        self.s.buffer.append({"type": "combat_update", "text": text})

    def _emit_scene(self, background: str = None, text: str = ""):
        """Emit a scene event with background image and optional text"""
        self.s.buffer.append(
            {"type": "scene", "data": {"background": background, "text": text}}
        )

    # ----- Formatting helpers -----
    def _format_monster_speech(self, mon: Dict[str, Any], line: Optional[str]) -> str:
        """Format a line as monster speech, ensuring the monster's name prefixes the text.

        Rules:
        - Format placeholders {monster} and {name} with the monster's name.
        - If the line starts with "Monster:", replace with "<Name>:".
        - If the line does not already start with a speaker prefix (like "X:"), prefix "<Name>: ".
        """
        try:
            name = str(mon.get("name", "Monster"))
        except Exception:
            name = "Monster"
        text = line or ""
        # Substitute common placeholders
        try:
            text = text.format(monster=name, name=name)
        except Exception:
            pass
        # Normalize whitespace
        text = str(text or "").lstrip()
        # Replace generic 'Monster:' speaker
        try:
            import re as _re

            text = _re.sub(
                r"^\s*Monster\s*:\s*", f"{name}: ", text, flags=_re.IGNORECASE
            )
        except Exception:
            # Fallback simple check
            if text.lower().startswith("monster:"):
                text = f"{name}: " + text.split(":", 1)[1].lstrip()
        # If no speaker prefix present, add the monster name
        try:
            import re as _re2

            if not _re2.match(r"^\s*[^:\n]{1,30}:\s", text):
                text = f"{name}: {text}"
        except Exception:
            if ":" not in text.split("\n", 1)[0]:
                text = f"{name}: {text}"
        return text

    # ---------- SHOP ----------
    def _shop_show_categories(self) -> List[Event]:
        # Clear first, then set the shop scene to avoid transition cancellation
        self._emit_clear()
        try:
            self._emit_scene("town_menu/shop.png")
        except Exception:
            pass
        # Mark we're at the root shop menu for proper Back handling
        self.s.subphase = "shop_root"
        self._emit_dialogue(
            get_dialogue("shop", "shop_header", None, self.s.character)
            or "\n=== Shop ==="
        )
        if self.s.character:
            self._emit_dialogue(f"Gold: {self.s.character.gold}g")
        items = [
            (
                "shop:weapons",
                get_dialogue("shop", "cat_weapons", None, self.s.character)
                or "1) Weapons",
            ),
            (
                "shop:armor",
                get_dialogue("shop", "cat_armor", None, self.s.character) or "2) Armor",
            ),
            (
                "shop:potions",
                get_dialogue("shop", "cat_potions", None, self.s.character)
                or "3) Potions",
            ),
            (
                "shop:spells",
                get_dialogue("shop", "cat_spells", None, self.s.character)
                or "4) Spells",
            ),
            (
                "shop:sell",
                get_dialogue("shop", "cat_sell", None, self.s.character)
                or "5) Sell items",
            ),
            (
                "shop:back",
                get_dialogue("shop", "cat_leave", None, self.s.character)
                or "6) Leave Shop",
            ),
        ]
        self._emit_menu(items)
        self._emit_state()
        return self._flush()

    # ---------- COMPANION ----------
    def _companion_menu(self) -> List[Event]:
        c = self.s.character
        self.s.subphase = "companion:menu"
        self._emit_clear()
        self._emit_dialogue(
            get_dialogue("system", "companion_header", None, c) or "=== Companion ==="
        )
        self._emit_menu(
            [
                ("comp:name", "1) Name companion"),
                ("comp:heal", "2) Heal companion (uses a healing potion)"),
                ("town", "3) Back"),
            ]
        )
        self._emit_state()
        return self._flush()

    def _companion_handle(self, action: str, payload: Dict[str, Any]) -> List[Event]:
        c = self.s.character
        if action == "comp:continue":
            return self._companion_menu()
        # Naming flow
        if action == "comp:name":
            self.s.subphase = "companion:name"
            self._emit_dialogue(
                # Prefer existing system.ask_name prompt
                get_dialogue("system", "ask_name", None, c)
                or "Enter new name:"
            )
            self._emit_prompt("name", "Enter new name:")
            self._emit_menu([("prompt:submit", "OK"), ("town", "Back")])
            self._emit_state()
            return self._flush()
        if self.s.subphase == "companion:name" and action == "prompt:submit":
            new_name = str((payload or {}).get("value") or "").strip()
            if not c or not c.companion:
                self._emit_dialogue(
                    get_dialogue("companion", "name_no_companion", None, c)
                    or "You have no companion to name."
                )
                return self._companion_menu()
            if new_name:
                c.companion.name = new_name
                msg = get_dialogue("companion", "name_success", None, c)
                try:
                    self._emit_dialogue(
                        msg.format(name=new_name)
                        if msg
                        else f"Your companion is now named {new_name}."
                    )
                except Exception:
                    self._emit_dialogue(f"Your companion is now named {new_name}.")
            return self._companion_menu()
        # Heal flow
        if action == "comp:heal":
            if not c or not c.companion:
                self._emit_dialogue(
                    get_dialogue("companion", "heal_no_companion", None, c)
                    or "You have no companion."
                )
                return self._companion_menu()
            if c.potions <= 0 and c.potion_uses.get("Healing", 0) <= 0:
                self._emit_dialogue(
                    get_dialogue("companion", "heal_no_potions", None, c)
                    or "You have no healing potions."
                )
                return self._companion_menu()
            # consume legacy or new healing
            if c.potions > 0:
                c.potions -= 1
            else:
                c.potion_uses["Healing"] = max(0, c.potion_uses.get("Healing", 0) - 1)
                if c.potion_uses.get("Healing", 0) <= 0:
                    c.potion_uses.pop("Healing", None)
            # New formula: ceil(CON/2) * 2d2, using player's CON as the potion's potency
            try:
                con = int(getattr(c, "attributes", {}).get("Constitution", 10))
            except Exception:
                con = 10
            mult = max(1, math.ceil(con / 2))
            heal = 0
            for _ in range(mult):
                heal += max(1, roll_damage("2d2"))
            comp = c.companion
            comp.hp = min(comp.max_hp, comp.hp + heal)
            msg = get_dialogue("companion", "heal_success", None, c)
            try:
                self._emit_dialogue(
                    msg.format(heal=heal)
                    if msg
                    else f"You heal your companion for {heal} HP."
                )
            except Exception:
                self._emit_dialogue(f"You heal your companion for {heal} HP.")
            self._emit_update_stats()
            self._emit_pause()
            self._emit_menu([("comp:continue", "Continue")])
            self._emit_state()
            return self._flush()
        # Default: show menu
        return self._companion_menu()

    # ---------- LEVEL UP ----------
    def _level_menu(self) -> List[Event]:
        c = self.s.character
        if not c:
            return self._flush()
        self._emit_clear()
        if c.unspent_stat_points <= 0:
            self._emit_dialogue(
                get_dialogue("system", "level_up", None, c)
                or "You have no unspent stat points."
            )
            # After this message, show town header + summary + menu
            return self._render_town_menu()
        # Show attributes to allocate a point
        self.s.subphase = "level:alloc"
        self._emit_dialogue(
            get_dialogue("system", "level_up", None, c)
            or "Allocate a stat point to an attribute:"
        )
        menu: List[Tuple[str, str]] = [("town", "Back")]
        attrs = [
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ]
        for i, a in enumerate(attrs, 1):
            menu.append((f"level:{a}", f"{i}) {a} ({c.attributes.get(a, 10)})"))
        self._emit_menu(menu)
        self._emit_state()
        return self._flush()

    def _level_handle(self, action: str) -> List[Event]:
        c = self.s.character
        if not c or not action.startswith("level:"):
            return self._level_menu()
        if action == "level:continue":
            return self._render_town_menu()
        if c.unspent_stat_points <= 0:
            return self._level_menu()
        attr = action.split(":", 1)[1]
        if attr not in (
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ):
            return self._level_menu()
        c.attributes[attr] = c.attributes.get(attr, 10) + 1
        c.unspent_stat_points -= 1
        self._emit_dialogue(f"You increase {attr} to {c.attributes.get(attr, 10)}.")
        self._emit_update_stats()
        # If points remain, keep showing the menu; otherwise return to town with header + summary
        if c.unspent_stat_points > 0:
            return self._level_menu()
        # Finalize with a clear-screen and Continue gating back to town
        self._emit_clear()
        try:
            msg = get_dialogue("system", "level_up_complete", None, c)
        except Exception:
            msg = None
        self._emit_dialogue(
            msg
            or f"Level-up allocation complete. {attr} is now {c.attributes.get(attr, 10)}."
        )
        self._emit_pause()
        self._emit_menu([("level:continue", "Continue")])
        self._emit_state()
        return self._flush()

    def _handle_shop(self, action: str) -> List[Event]:
        if action == "shop:back":
            # Context-aware Back: if inside a sub-menu/category, go to shop root;
            # otherwise leave shop back to town.
            sub = self.s.subphase or ""
            if sub.startswith("shop_cat:") or sub in ("sell", "shop_sell"):
                return self._shop_show_categories()
            self.s.phase = "town"
            self._emit_clear()
            return self._render_town_menu()
        if action == "shop:continue":
            # Return to the last viewed category if known
            sub = self.s.subphase or ""
            if sub.startswith("shop_cat:"):
                cat = sub.split(":", 1)[1]
                return self._shop_list_category(cat)
            return self._shop_show_categories()
        if action in ("shop:weapons", "shop:armor", "shop:potions", "shop:spells"):
            return self._shop_list_category(action.split(":")[1])
        if action == "shop:sell":
            return self._shop_sell_menu()
        if action == "shop:sell_continue":
            return self._shop_sell_menu()
        if action.startswith("shop:buy:"):
            _, _, payload = action.partition(":buy:")
            return self._shop_buy(payload)
        if action.startswith("shop:sellsel:"):
            # Process a selected item to sell
            _, _, payload = action.partition(":sellsel:")
            return self._shop_sell_selected(payload)
        if action.startswith("shop:sellconfirm:"):
            _, _, payload = action.partition(":sellconfirm:")
            return self._shop_sell_confirm(payload)
        # default
        return self._shop_show_categories()

    def _shop_list_category(self, cat: str) -> List[Event]:
        char = self.s.character
        self._emit_clear()
        # Remember last visited category for Continue routing
        self.s.subphase = f"shop_cat:{cat}"
        data = []
        title = ""
        if cat == "weapons":
            data = [
                w
                for w in load_weapons()
                if int(w.get("price", 0)) > 0
                and w.get("availability", "shop") != "labyrinth"
            ]
            title = (
                get_dialogue("shop", "weapons_header", None, char) or "=== Weapons ==="
            )
        elif cat == "armor":
            data = [
                a
                for a in load_armors()
                if int(a.get("price", 0)) > 0
                and a.get("availability", "shop") != "labyrinth"
            ]
            title = get_dialogue("shop", "armor_header", None, char) or "=== Armor ==="
        elif cat == "potions":
            data = [
                p for p in load_potions() if int(p.get("cost", p.get("price", 0))) > 0
            ]
            title = (
                get_dialogue("shop", "potions_header", None, char) or "=== Potions ==="
            )
        elif cat == "spells":
            data = [s for s in load_spells() if int(s.get("cost", 0)) > 0]
            title = (
                get_dialogue("shop", "spells_header", None, char) or "=== Spells ==="
            )
        self._emit_dialogue(title)
        if char:
            self._emit_dialogue(f"Gold: {char.gold}g")
        menu: List[Tuple[str, str]] = [("shop:back", "1) Back to main shop")]
        idx = 2
        for item in data:
            if cat in ("weapons", "armor"):
                name = item.get("name")
                price = int(item.get("price", 0))
                label = f"{idx}) {name} ({'AC '+str(item.get('armor_class')) if cat=='armor' else item.get('damage_die','1d4')}), {price}g"
            elif cat == "potions":
                name = item.get("name")
                price = int(item.get("cost", item.get("price", 0)))
                uses = int(item.get("uses", 1))
                label = f"{idx}) {name} ({uses} uses) ({price}g)"
            else:
                name = item.get("name")
                price = int(item.get("cost", 0))
                uses = int(item.get("uses", 1))
                label = f"{idx}) {name} ({uses} uses) ({price}g)"
            menu.append((f"shop:buy:{cat}:{name}", label))
            idx += 1
        self._emit_menu(menu)
        self._emit_state()
        return self._flush()

    def _shop_buy(self, payload: str) -> List[Event]:
        # payload is like 'weapons:Sword' etc.
        try:
            cat, name = payload.split(":", 1)
        except ValueError:
            return self._shop_show_categories()
        c = self.s.character
        if not c:
            return self._shop_show_categories()
        if cat == "weapons":
            src = [w for w in load_weapons() if w.get("name") == name]
            if not src:
                return self._shop_list_category("weapons")
            item = src[0]
            price = int(item.get("price", 0))
            if c.gold < price:
                self._emit_dialogue(
                    get_dialogue("shop", "no_gold", None, c) or "Not enough gold."
                )
                # Explicit shortfall details
                try:
                    self._emit_dialogue(f"You need {price}g but have {c.gold}g.")
                except Exception:
                    pass
                # Pause and allow returning to last category
                self._emit_pause()
                self._emit_menu([("shop:continue", "Continue")])
                self._emit_state()
                return self._flush()
            from .entities import Weapon

            c.gold -= price
            c.weapons.append(
                Weapon(
                    name=item.get("name", "Weapon"),
                    damage_die=item.get("damage_die", "1d4"),
                )
            )
            self._emit_dialogue(
                get_dialogue("shop", "buy", None, c)
                or f"Purchased {name}. Use Inventory to equip it."
            )
            # Extra clarity: show what was bought and for how much
            try:
                self._emit_dialogue(f"You bought {name} for {price}g.")
            except Exception:
                pass
            self._emit_update_stats()
            self._emit_pause()
            self._emit_menu([("shop:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if cat == "armor":
            src = [a for a in load_armors() if a.get("name") == name]
            if not src:
                return self._shop_list_category("armor")
            item = src[0]
            price = int(item.get("price", 0))
            if c.gold < price:
                self._emit_dialogue(
                    get_dialogue("shop", "no_gold", None, c) or "Not enough gold."
                )
                # Explicit shortfall details
                try:
                    self._emit_dialogue(f"You need {price}g but have {c.gold}g.")
                except Exception:
                    pass
                self._emit_pause()
                self._emit_menu([("shop:continue", "Continue")])
                self._emit_state()
                return self._flush()
            from .entities import Armor

            c.gold -= price
            new_armor = Armor(
                name=item.get("name", "Armor"),
                armor_class=int(item.get("armor_class", 12)),
            )
            c.armors_owned.append(new_armor)
            c.armor = new_armor
            self._emit_dialogue(
                get_dialogue("shop", "buy", None, c)
                or f"Purchased and equipped {name}."
            )
            # Extra clarity: show what was bought and for how much
            try:
                self._emit_dialogue(f"You bought {name} for {price}g.")
            except Exception:
                pass
            self._emit_update_stats()
            self._emit_pause()
            self._emit_menu([("shop:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if cat == "potions":
            src = [p for p in load_potions() if p.get("name") == name]
            if not src:
                return self._shop_list_category("potions")
            item = src[0]
            price = int(item.get("cost", item.get("price", 0)))
            uses = int(item.get("uses", 1))
            if c.gold < price:
                self._emit_dialogue(
                    get_dialogue("shop", "no_gold", None, c) or "Not enough gold."
                )
                # Explicit shortfall details
                try:
                    self._emit_dialogue(f"You need {price}g but have {c.gold}g.")
                except Exception:
                    pass
                self._emit_pause()
                self._emit_menu([("shop:continue", "Continue")])
                self._emit_state()
                return self._flush()
            c.gold -= price
            c.potion_uses[name] = c.potion_uses.get(name, 0) + uses
            if name.lower() == "healing":
                c.potions += 1
            self._emit_dialogue(
                get_dialogue("shop", "buy", None, c)
                or f"Purchased {name} (+{uses} uses)."
            )
            # Extra clarity: show what was bought and for how much
            try:
                self._emit_dialogue(f"You bought {name} for {price}g.")
            except Exception:
                pass
            self._emit_update_stats()
            self._emit_pause()
            self._emit_menu([("shop:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if cat == "spells":
            src = [s for s in load_spells() if s.get("name") == name]
            if not src:
                return self._shop_list_category("spells")
            item = src[0]
            price = int(item.get("cost", 0))
            uses = int(item.get("uses", 1))
            if c.gold < price:
                self._emit_dialogue(
                    get_dialogue("shop", "no_gold", None, c) or "Not enough gold."
                )
                # Explicit shortfall details
                try:
                    self._emit_dialogue(f"You need {price}g but have {c.gold}g.")
                except Exception:
                    pass
                self._emit_pause()
                self._emit_menu([("shop:continue", "Continue")])
                self._emit_state()
                return self._flush()
            c.gold -= price
            c.spells[name] = c.spells.get(name, 0) + uses
            self._emit_dialogue(
                get_dialogue("shop", "buy", None, c)
                or f"Purchased {name} (+{uses} uses)."
            )
            # Extra clarity: show what was bought and for how much
            try:
                self._emit_dialogue(f"You bought {name} for {price}g.")
            except Exception:
                pass
            self._emit_update_stats()
            self._emit_pause()
            self._emit_menu([("shop:continue", "Continue")])
            self._emit_state()
            return self._flush()
        return self._shop_show_categories()

    # ---------- SHOP SELL FLOW ----------
    def _shop_sell_menu(self) -> List[Event]:
        c = self.s.character
        self._emit_clear()
        # Mark we're in sell context so Back returns to main shop categories
        self.s.subphase = "shop_sell"
        self._emit_dialogue(
            get_dialogue("shop", "sell_header", None, c) or "=== Sell Items ==="
        )
        self._emit_dialogue(f"Gold: {c.gold}g")
        # Build sellable lists (exclude equipped/damaged)
        sellable: List[Tuple[str, int, str]] = []  # (kind, index, label)
        # Weapons
        for i, w in enumerate(c.weapons):
            if getattr(w, "damaged", False):
                continue
            if i == c.equipped_weapon_index:
                continue
            sellable.append(("w", i, w.name))
        # Armors (owned and not currently equipped)
        for i, a in enumerate(c.armors_owned):
            if getattr(a, "damaged", False):
                continue
            if c.armor and a.name == c.armor.name:
                continue
            sellable.append(("a", i, a.name))
        # Magic items (non-cursed)
        for i, mi in enumerate(c.magic_items):
            if getattr(mi, "cursed", False):
                continue
            sellable.append(("m", i, getattr(mi, "name", "Mysterious Item")))

        if not sellable:
            self._emit_dialogue(
                get_dialogue("shop", "no_sellable", None, c)
                or "You have nothing that can be sold in the shop."
            )
            self._emit_menu([("shop:back", "1) Back")])
            self._emit_state()
            return self._flush()

        menu: List[Tuple[str, str]] = [("shop:back", "1) Back")]
        idx = 2
        self.s.subphase = "sell"  # mark context
        for kind, i, label in sellable:
            menu.append((f"shop:sellsel:{kind}:{i}", f"{idx}) {label}"))
            idx += 1
        self._emit_dialogue(
            get_dialogue("shop", "sellable_items", None, c) or "Sellable items:"
        )
        self._emit_menu(menu)
        self._emit_state()
        return self._flush()

    def _shop_item_base_price(self, kind: str, name: str) -> int:
        # Attempt to recover shop price for weapons/armor; default for others
        if kind == "w":
            src = [w for w in load_weapons() if w.get("name") == name]
            if src:
                return int(src[0].get("price", 0))
        if kind == "a":
            src = [a for a in load_armors() if a.get("name") == name]
            if src:
                return int(src[0].get("price", 0))
        # Magic items or unknown — assign a nominal value
        return 100

    def _shop_haggle_price(self, base_price: int) -> int:
        c = self.s.character
        # Start from half price
        price = int(max(1, base_price * 0.5))
        cha = int(c.attributes.get("Charisma", 10))
        # Charisma sway +/- up to 20%
        if cha >= 15:
            price = int(price * 1.2)
        elif cha <= 6:
            price = int(price * 0.8)
        # Random market variance +/- 10%
        variance = 0.9 + random.random() * 0.2
        price = int(max(1, price * variance))
        return price

    def _shop_sell_selected(self, payload: str) -> List[Event]:
        # payload "{kind}:{index}"
        c = self.s.character
        try:
            kind, idxs = payload.split(":", 1)
            index = int(idxs)
        except Exception:
            return self._shop_sell_menu()
        name = None
        if kind == "w":
            if index < 0 or index >= len(c.weapons):
                return self._shop_sell_menu()
            w = c.weapons[index]
            if getattr(w, "damaged", False) or index == c.equipped_weapon_index:
                # Cannot sell damaged or equipped
                self._emit_dialogue(
                    get_dialogue("shop", "cannot_sell_equipped", None, c)
                    or "You cannot sell an equipped weapon. Unequip it first."
                )
                return self._shop_sell_menu()
            name = w.name
        elif kind == "a":
            if index < 0 or index >= len(c.armors_owned):
                return self._shop_sell_menu()
            a = c.armors_owned[index]
            if getattr(a, "damaged", False) or (c.armor and a.name == c.armor.name):
                self._emit_dialogue(
                    get_dialogue("shop", "cannot_sell_equipped", None, c)
                    or "You cannot sell equipped armor. Unequip it first."
                )
                return self._shop_sell_menu()
            name = a.name
        else:
            if index < 0 or index >= len(c.magic_items):
                return self._shop_sell_menu()
            mi = c.magic_items[index]
            if getattr(mi, "cursed", False):
                return self._shop_sell_menu()
            name = getattr(mi, "name", "Mysterious Item")
        base = self._shop_item_base_price(kind, name)
        offer = self._shop_haggle_price(base)
        info = (
            get_dialogue("shop", "haggle_info", None, c)
            or "Original shop price: {price}g"
        )
        self._emit_dialogue(info.format(price=base))
        succ = (
            get_dialogue("shop", "haggle_success", None, c)
            or "Alright, alright — you win. {price} gold."
        )
        try:
            self._emit_dialogue(succ.format(price=offer))
        except Exception:
            self._emit_dialogue(f"Offer: {offer} gold.")
        # Store pending sale in subphase for confirm step
        self.s.subphase = f"sell_pending|{kind}|{index}|{offer}"
        self._emit_menu(
            [
                ("shop:sellconfirm:yes", "1) Confirm sale"),
                ("shop:sellconfirm:no", "2) Cancel"),
            ]
        )
        self._emit_state()
        return self._flush()

    def _shop_sell_confirm(self, payload: str) -> List[Event]:
        c = self.s.character
        if not (self.s.subphase or "").startswith("sell_pending|"):
            return self._shop_sell_menu()
        _, kind, idxs, offers = (self.s.subphase or "").split("|", 3)
        index = int(idxs)
        offer = int(offers)
        if payload.endswith("no"):
            self._emit_dialogue(
                get_dialogue("shop", "sale_cancelled", None, c) or "Sale cancelled."
            )
            self._emit_pause()
            self._emit_menu([("shop:sell_continue", "Continue")])
            self._emit_state()
            return self._flush()
        # Proceed with sale
        sold_name = None
        if kind == "w" and 0 <= index < len(c.weapons):
            sold_name = c.weapons[index].name
            del c.weapons[index]
            if c.equipped_weapon_index == index:
                c.equipped_weapon_index = -1
        elif kind == "a" and 0 <= index < len(c.armors_owned):
            sold_name = c.armors_owned[index].name
            del c.armors_owned[index]
        elif kind == "m" and 0 <= index < len(c.magic_items):
            sold_name = getattr(c.magic_items[index], "name", "Mysterious Item")
            del c.magic_items[index]
        if sold_name:
            c.gold += offer
            msg = (
                get_dialogue("shop", "sold_item", None, c)
                or "Sold {name} for {price}g."
            )
            try:
                self._emit_dialogue(msg.format(name=sold_name, price=offer))
            except Exception:
                self._emit_dialogue(f"Sold {sold_name} for {offer}g.")
            # Extra clarity: repeat sale summary
            try:
                self._emit_dialogue(f"You sold {sold_name} for {offer}g.")
            except Exception:
                pass
            self._emit_update_stats()
        self._emit_pause()
        self._emit_menu([("shop:sell_continue", "Continue")])
        self._emit_state()
        return self._flush()

    # ---------- INVENTORY ----------
    def _inventory_show(self) -> List[Event]:
        c = self.s.character
        self._emit_clear()
        self._emit_dialogue(
            get_dialogue("system", "inventory_header", None, c) or "\n=== Inventory ==="
        )
        # Equipped lines
        if c:
            cw = "Unarmed"
            damage_display = "—"
            if 0 <= c.equipped_weapon_index < len(c.weapons):
                w = c.weapons[c.equipped_weapon_index]
                cw = w.name + (" (damaged)" if getattr(w, "damaged", False) else "")
                try:
                    damage_display = getattr(w, "damage_die", "1d2")
                except Exception:
                    damage_display = "1d2"
            line = get_dialogue("system", "inventory_equipped_weapon", None, c)
            if line:
                try:
                    # Support both {name} and {weapon} placeholders
                    self._emit_dialogue(
                        line.format(name=cw, weapon=cw, damage=damage_display)
                    )
                except Exception:
                    self._emit_dialogue(f"Equipped weapon: {cw}")
            else:
                self._emit_dialogue(f"Equipped weapon: {cw}")

            armor_display = "None"
            if c.armor:
                armor_display = c.armor.name + (
                    " (damaged)" if getattr(c.armor, "damaged", False) else ""
                )
            line = get_dialogue("system", "inventory_equipped_armor", None, c)
            if line:
                try:
                    # Support both {name} and {armor} placeholders, and {ac}
                    self._emit_dialogue(
                        line.format(
                            name=armor_display,
                            armor=armor_display,
                            ac=(c.armor.armor_class if c.armor else 10),
                        )
                    )
                except Exception:
                    self._emit_dialogue(
                        f"Equipped armor: {armor_display} (AC {c.armor.armor_class if c.armor else 10})"
                    )
            else:
                self._emit_dialogue(
                    f"Equipped armor: {armor_display} (AC {c.armor.armor_class if c.armor else 10})"
                )
        g = lambda key, dflt: get_dialogue("inventory", key, None, c) or dflt
        menu = [
            ("inv:weapon", g("menu_equip_weapon", "1) Equip weapon")),
            ("inv:armor", g("menu_equip_armor", "2) Equip armor")),
            ("inv:potions", g("menu_potions", "3) View potions")),
            ("inv:unequip_weapon", g("menu_unequip_weapon", "4) Unequip weapon")),
            ("inv:unequip_armor", g("menu_unequip_armor", "5) Unequip armor")),
            ("inv:back", g("menu_back", "6) Back")),
        ]
        self._emit_menu(menu)
        self._emit_state()
        return self._flush()

    def _handle_inventory(self, action: str) -> List[Event]:
        c = self.s.character
        if action == "inv:continue":
            return self._inventory_show()
        if action == "inv:back":
            self.s.phase = "town"
            self._emit_clear()
            return self._render_town_menu()
        if action == "inv:weapon":
            self._emit_clear()
            if not (c and c.weapons):
                self._emit_dialogue(
                    get_dialogue("inventory", "no_weapons", None, c)
                    or "You have no weapons."
                )
                return self._inventory_show()
            menu = [
                (
                    "inv:weapon:back",
                    get_dialogue("inventory", "menu_back", None, c) or "1) Back",
                )
            ]
            idx = 2
            for i, w in enumerate(c.weapons):
                label = w.name + (" (damaged)" if getattr(w, "damaged", False) else "")
                menu.append(
                    (
                        f"inv:weapon:set:{i}",
                        f"{idx}) {label} ({getattr(w,'damage_die','1d4')})",
                    )
                )
                idx += 1
            self._emit_menu(menu)
            self._emit_state()
            return self._flush()
        if action.startswith("inv:weapon:set:"):
            i = int(action.rsplit(":", 1)[-1])
            if c and 0 <= i < len(c.weapons):
                c.equipped_weapon_index = i
                msg = (
                    get_dialogue("inventory", "equipped_weapon", None, c)
                    or "Equipped {name}."
                )
                try:
                    self._emit_dialogue(msg.format(name=c.weapons[i].name))
                except Exception:
                    self._emit_dialogue(f"Equipped {c.weapons[i].name}.")
            self._emit_pause()
            self._emit_menu([("inv:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "inv:weapon:back":
            return self._inventory_show()
        if action == "inv:armor":
            self._emit_clear()
            if not c or (not c.armors_owned and not c.armor):
                self._emit_dialogue(
                    get_dialogue("inventory", "no_armor", None, c)
                    or "You have no armor."
                )
                return self._inventory_show()
            options = []
            if c.armor:
                options.append(c.armor)
            options.extend(
                a for a in c.armors_owned if (not c.armor or a.name != c.armor.name)
            )
            menu = [
                (
                    "inv:armor:back",
                    get_dialogue("inventory", "menu_back", None, c) or "1) Back",
                )
            ]
            idx = 2
            for i, a in enumerate(options):
                label = a.name + (" (damaged)" if getattr(a, "damaged", False) else "")
                menu.append(
                    (f"inv:armor:set:{i}", f"{idx}) {label} (AC {a.armor_class})")
                )
                idx += 1
            # stash options in subphase for quick lookup
            self.s.subphase = "|".join([a.name for a in options])
            self._emit_menu(menu)
            self._emit_state()
            return self._flush()
        if action.startswith("inv:armor:set:"):
            if not c:
                return self._inventory_show()
            index = int(action.rsplit(":", 1)[-1])
            names = (self.s.subphase or "").split("|") if self.s.subphase else []
            if 0 <= index < len(names):
                name = names[index]
                # find armor by name in owned or current
                cand = [
                    a
                    for a in ([c.armor] if c.armor else []) + c.armors_owned
                    if a and a.name == name
                ]
                if cand:
                    c.armor = cand[0]
                    msg = (
                        get_dialogue("inventory", "equipped_armor", None, c)
                        or "Equipped {name}."
                    )
                    try:
                        self._emit_dialogue(msg.format(name=c.armor.name))
                    except Exception:
                        self._emit_dialogue(f"Equipped {c.armor.name}.")
            self._emit_pause()
            self._emit_menu([("inv:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "inv:armor:back":
            return self._inventory_show()
        if action == "inv:potions":
            self._emit_clear()
            if not c:
                return self._inventory_show()
            if not c.potion_uses and c.potions <= 0:
                self._emit_dialogue(
                    get_dialogue("inventory", "no_potions", None, c)
                    or "You have no potions."
                )
            else:
                self._emit_dialogue(
                    get_dialogue("inventory", "potions_header", None, c) or "Potions:"
                )
                if c.potions > 0:
                    base = (
                        get_dialogue("inventory", "potion_heal_legacy", None, c)
                        or "Healing (legacy): {count}"
                    )
                    try:
                        self._emit_dialogue(base.format(count=c.potions))
                    except Exception:
                        self._emit_dialogue(f"Healing (legacy): {c.potions}")
                for name, uses in c.potion_uses.items():
                    base = (
                        get_dialogue("inventory", "potion_uses", None, c)
                        or "{name}: {uses} uses"
                    )
                    try:
                        self._emit_dialogue(base.format(name=name, uses=uses))
                    except Exception:
                        self._emit_dialogue(f"{name}: {uses} uses")
            self._emit_pause()
            return self._inventory_show()
        if action == "inv:unequip_weapon":
            if c and 0 <= c.equipped_weapon_index < len(c.weapons):
                msg = (
                    get_dialogue("inventory", "unequipped_weapon", None, c)
                    or "Unequipped {name}."
                )
                try:
                    self._emit_dialogue(
                        msg.format(name=c.weapons[c.equipped_weapon_index].name)
                    )
                except Exception:
                    self._emit_dialogue(
                        f"Unequipped {c.weapons[c.equipped_weapon_index].name}."
                    )
                c.equipped_weapon_index = -1
            else:
                self._emit_dialogue(
                    get_dialogue("inventory", "no_weapon_equipped", None, c)
                    or "No weapon is currently equipped."
                )
            self._emit_pause()
            self._emit_menu([("inv:continue", "Continue")])
            self._emit_state()
            return self._flush()
        if action == "inv:unequip_armor":
            if c and c.armor:
                msg = (
                    get_dialogue("inventory", "unequipped_armor", None, c)
                    or "Unequipped {name}."
                )
                try:
                    self._emit_dialogue(msg.format(name=c.armor.name))
                except Exception:
                    self._emit_dialogue(f"Unequipped {c.armor.name}.")
                c.armor = None
            else:
                self._emit_dialogue(
                    get_dialogue("inventory", "no_armor_equipped", None, c)
                    or "No armor is currently equipped."
                )
            self._emit_pause()
            self._emit_menu([("inv:continue", "Continue")])
            self._emit_state()
            return self._flush()
        # default
        return self._inventory_show()

    # ---------- TRAIN ----------
    def _train_menu(self) -> List[Event]:
        c = self.s.character
        if not c:
            return self._flush()
        if c.trained_times >= 7:
            self._emit_dialogue("Garron: You cannot train any further.")
            self._emit_menu(self._town_choices())
            self._emit_state()
            return self._flush()
        cost = 50 * (c.trained_times + 1)
        if c.gold < cost:
            self._emit_dialogue(
                f"Garron: Training costs {cost}g; you don't have enough."
            )
            # Show shortfall details and gate with Continue only
            try:
                self._emit_dialogue(f"You need {cost}g but have {c.gold}g.")
            except Exception:
                pass
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        attrs = list(c.attributes.keys())
        self._emit_dialogue("Garron: Choose an attribute to train:")
        menu = [("town", f"Back ({cost}g)")]
        for i, name in enumerate(attrs, 1):
            menu.append(
                (
                    f"train:{name}",
                    f"{i}) {name} ({c.attributes.get(name,10)}) - Cost: {cost}g",
                )
            )
        self._emit_menu(menu)
        self._emit_state()
        return self._flush()

    def _train_handle(self, action: str) -> List[Event]:
        c = self.s.character
        if not c or not action.startswith("train:"):
            return self._render_town_menu()
        # Validate attribute
        attr = action.split(":", 1)[1]
        if attr not in (
            "Strength",
            "Dexterity",
            "Constitution",
            "Intelligence",
            "Wisdom",
            "Charisma",
            "Perception",
        ):
            return self._train_menu()
        cost = 50 * (c.trained_times + 1)
        if c.gold < cost:
            self._emit_dialogue(
                f"Garron: Training costs {cost}g; you don't have enough."
            )
            try:
                self._emit_dialogue(f"You need {cost}g but have {c.gold}g.")
            except Exception:
                pass
            self._emit_pause()
            self._emit_menu([("town", "Continue")])
            self._emit_state()
            return self._flush()
        # Perform training
        c.gold -= cost
        try:
            self._emit_dialogue(f"Paid {cost}g.")
        except Exception:
            pass
        old_val = int(c.attributes.get(attr, 10))
        c.attributes[attr] = old_val + 1
        # Constitution grants +5 max HP per increase
        if attr == "Constitution":
            try:
                c.max_hp += 5
            except Exception:
                c.max_hp = int(c.max_hp) + 5
        # Track training counts per attribute
        try:
            tmap = getattr(c, "attribute_training", {})
            tmap[attr] = int(tmap.get(attr, 0)) + 1
            c.attribute_training = tmap
        except Exception:
            pass
        c.trained_times += 1
        self._emit_dialogue(f"You train {attr} to {c.attributes.get(attr, 10)}.")
        self._emit_update_stats()
        # Gate back to town
        self._emit_pause()
        self._emit_menu([("town", "Continue")])
        self._emit_state()
        return self._flush()

    def _weaponsmith_menu(self) -> List[Event]:
        c = self.s.character
        # Clear first, then set scene to avoid transition cancellation
        self._emit_clear()
        try:
            self._emit_scene("town_menu/weaponsmith.png")
        except Exception:
            pass
        self._emit_dialogue(
            get_dialogue("shop", "shop_header", None, c) or "=== Shop ==="
        )
        from .data_loader import get_npc_dialogue

        self._emit_dialogue(
            get_npc_dialogue("town", "weaponsmith_thorin", None, c)
            or "Thorin: Blacksmith at your service."
        )
        self._emit_dialogue(f"Gold: {c.gold}g")
        damaged_weapons = [w for w in c.weapons if getattr(w, "damaged", False)]
        damaged_armors = [
            a
            for a in (c.armors_owned + ([c.armor] if c.armor else []))
            if a and getattr(a, "damaged", False)
        ]
        if not damaged_weapons and not damaged_armors:
            self._emit_dialogue(
                get_dialogue("town", "no_damaged_equipment", None, c)
                or "All your equipment is in good condition."
            )
            # Return to town menu with header + summary after this message
            return self._render_town_menu()
        items: List[Tuple[str, str]] = [
            (
                "town",
                (get_dialogue("town", "back_option", None, c) or "Back").replace(
                    "Back", "1) Back"
                ),
            )
        ]
        idx = 2
        if damaged_weapons:
            self._emit_dialogue(
                get_dialogue("town", "damaged_weapons", None, c) or "Damaged weapons:"
            )
            for i, w in enumerate(damaged_weapons):
                label_tpl = (
                    get_dialogue("town", "damaged_weapon_option", None, c)
                    or "{idx}) {name} (reduced effectiveness)"
                )
                try:
                    label = label_tpl.format(idx=idx, name=w.name)
                except Exception:
                    label = f"{idx}) {w.name} (reduced effectiveness)"
                items.append((f"repair:w:{i}", label))
                idx += 1
        if damaged_armors:
            self._emit_dialogue(
                get_dialogue("town", "damaged_armors", None, c) or "Damaged armor:"
            )
            for j, a in enumerate(damaged_armors):
                label_tpl = (
                    get_dialogue("town", "damaged_armor_option", None, c)
                    or "{idx}) {name} (reduced protection)"
                )
                try:
                    label = label_tpl.format(idx=idx, name=a.name)
                except Exception:
                    label = f"{idx}) {a.name} (reduced protection)"
                items.append((f"repair:a:{j}", label))
                idx += 1
        # Stash lookup lists for later resolution
        self.s.subphase = "repair_ctx"
        self.s.combat["repair_lists"] = {
            "weapons": damaged_weapons,
            "armors": damaged_armors,
        }
        self._emit_menu(items)
        self._emit_state()
        return self._flush()

    def _weaponsmith_handle(self, action: str) -> List[Event]:
        c = self.s.character
        ctx = self.s.combat.get("repair_lists", {"weapons": [], "armors": []})
        COST = 30
        try:
            _, kind, idxs = action.split(":", 2)
        except ValueError:
            return self._weaponsmith_menu()
        if kind == "w":
            try:
                i = int(idxs)
                w = ctx.get("weapons", [])[i]
            except Exception:
                return self._weaponsmith_menu()
            if c.gold < COST:
                msg = (
                    get_dialogue("town", "repair_costs", None, c)
                    or "Repair costs {cost}g; you don't have enough."
                )
                try:
                    self._emit_dialogue(msg.format(cost=COST))
                except Exception:
                    self._emit_dialogue(f"Repair costs {COST}g; you don't have enough.")
                try:
                    self._emit_dialogue(f"You need {COST}g but have {c.gold}g.")
                except Exception:
                    pass
                return self._weaponsmith_menu()
            c.gold -= COST
            try:
                self._emit_dialogue(f"Paid {COST}g.")
            except Exception:
                pass
            setattr(w, "damaged", False)
            msg = (
                get_dialogue("town", "repair_success_weapon", None, c)
                or "Your {name} has been repaired! (Cost: {cost}g)"
            )
            try:
                self._emit_dialogue(msg.format(name=w.name, cost=COST))
            except Exception:
                self._emit_dialogue(f"Your {w.name} has been repaired! (Cost: {COST}g)")
            self._emit_update_stats()
            return self._weaponsmith_menu()
        if kind == "a":
            try:
                j = int(idxs)
                a = ctx.get("armors", [])[j]
            except Exception:
                return self._weaponsmith_menu()
            if c.gold < COST:
                msg = (
                    get_dialogue("town", "repair_costs", None, c)
                    or "Repair costs {cost}g; you don't have enough."
                )
                try:
                    self._emit_dialogue(msg.format(cost=COST))
                except Exception:
                    self._emit_dialogue(f"Repair costs {COST}g; you don't have enough.")
                try:
                    self._emit_dialogue(f"You need {COST}g but have {c.gold}g.")
                except Exception:
                    pass
                return self._weaponsmith_menu()
            c.gold -= COST
            try:
                self._emit_dialogue(f"Paid {COST}g.")
            except Exception:
                pass
            setattr(a, "damaged", False)
            msg = (
                get_dialogue("town", "repair_success_armor", None, c)
                or "Your {name} has been repaired and will restore protection. (Cost: {cost}g)"
            )
            try:
                self._emit_dialogue(msg.format(name=a.name, cost=COST))
            except Exception:
                self._emit_dialogue(
                    f"Your {a.name} has been repaired and will restore protection. (Cost: {COST}g)"
                )
            self._emit_update_stats()
            return self._weaponsmith_menu()
        return self._weaponsmith_menu()

    # ---------- GAMBLING ----------
    def _gamble_start(self) -> List[Event]:
        c = self.s.character
        self.s.gamble = {}
        self.s.subphase = "gamble:mode"
        # Clear, then set gambling scene to avoid transition cancellation
        self._emit_clear()
        try:
            self._emit_scene("town_menu/gambling.png")
        except Exception:
            pass
        from .data_loader import get_npc_dialogue

        intro = get_npc_dialogue("town", "gambler_seth", None, c)
        if intro:
            self._emit_dialogue(intro)
        prompt = (
            get_dialogue("system", "choose_mode_prompt", None, c)
            or "Which mode do you want to play?"
        )
        self._emit_dialogue(prompt)
        self._emit_menu(
            [
                ("gamble:mode:exact", "1) Exact guess"),
                ("gamble:mode:range", "2) Range guess"),
                ("town", "3) Back"),
            ]
        )
        self._emit_state()
        return self._flush()

    def _gamble_handle(
        self, action: Optional[str], payload: Dict[str, Any]
    ) -> List[Event]:
        c = self.s.character
        g = self.s.gamble
        sub = self.s.subphase or ""
        # Mode selection
        if sub == "gamble:mode":
            if action == "gamble:mode:exact":
                self.s.gamble = {"mode": "exact", "bet": 0}
                return self._gamble_bet_menu()
            if action == "gamble:mode:range":
                self.s.gamble = {"mode": "range", "bet": 0}
                return self._gamble_bet_menu()
            # otherwise re-show
            return self._gamble_start()

        # Bet adjustments
        if sub == "gamble:bet":
            # ensure bet key exists
            g.setdefault("bet", 0)
            if action and action.startswith("bet:"):
                inc = 0
                if action == "bet:+5":
                    inc = 5
                elif action == "bet:+10":
                    inc = 10
                elif action == "bet:+50":
                    inc = 50
                elif action == "bet:+100":
                    inc = 100
                elif action == "bet:back":
                    return self._gamble_start()
                elif action == "bet:ok":
                    # Validate bet
                    bet = int(g.get("bet", 0))
                    # Context-specific validation messages
                    min_bet = 5
                    if bet < min_bet:
                        # Too low: show explicit minimum message
                        self._emit_dialogue(
                            f"That wager won't do — minimum {min_bet} gold."
                        )
                        return self._gamble_bet_menu()
                    if bet > (c.gold if c else 0):
                        # Too high for wallet
                        gold = c.gold if c else 0
                        self._emit_dialogue(
                            get_dialogue("town", "bet_range", None, c)
                            or f"You don't have enough gold for that bet. Max: {gold}g."
                        )
                        return self._gamble_bet_menu()
                    # Proceed to mode specifics
                    if g.get("mode") == "exact":
                        return self._gamble_exact_choose_die()
                    else:
                        return self._gamble_range_menu()
                if inc:
                    g["bet"] = min((c.gold if c else 0), g.get("bet", 0) + inc)
                return self._gamble_bet_menu()

        # Exact: choose die
        if sub == "gamble:exact:die":
            if action == "gamble:back":
                return self._gamble_bet_menu()
            if action in ("exact:d20", "exact:d10", "exact:d6"):
                sides = (
                    20
                    if action.endswith("d20")
                    else (10 if action.endswith("d10") else 6)
                )
                g["die_sides"] = sides
                # Prompt for exact guess
                self.s.subphase = "gamble:exact:guess"
                self._emit_clear()
                # Ensure {sides} is formatted even when dialogue text contains a placeholder
                line = get_dialogue("town", "pick_number", None, c)
                try:
                    msg = (line or "Pick a number between 1 and {sides}.").format(
                        sides=sides
                    )
                except Exception:
                    msg = f"Pick a number between 1 and {sides}."
                self._emit_dialogue(msg)
                # Build number buttons 1..sides plus Back, with Back numbered last
                menu = [(f"guess:{i}", f"{i}") for i in range(1, sides + 1)]
                menu.append(("gamble:back", f"{len(menu)+1}) Back"))
                self._emit_menu(menu)
                self._emit_state()
                return self._flush()
            # re-show
            return self._gamble_exact_choose_die()

        # Exact: handle guess submit
        if sub == "gamble:exact:guess":
            if action == "gamble:back":
                return self._gamble_exact_choose_die()
            if not (action and action.startswith("guess:")):
                return self._gamble_invalid()
            # parse guess from action id
            try:
                guess = int(action.split(":", 1)[1])
            except Exception:
                return self._gamble_invalid()
            sides = int(g.get("die_sides", 20))
            if guess < 1 or guess > sides:
                # Re-show the guess menu
                return self._gamble_invalid()
            # Record and announce player's choice
            g["guess"] = guess
            self._emit_dialogue(f"You chose {guess} on a d{sides}.")
            # Roll and resolve
            roll = 0
            try:
                roll = roll_damage(f"1d{sides}")
            except Exception:
                import random as _r

                roll = _r.randint(1, sides)
            self._emit_dialogue(f"You roll: {roll}")
            bet = int(g.get("bet", 0))
            if roll == guess:
                mult = 11 if sides == 20 else (6 if sides == 10 else 3)
                win = bet * mult
                c.gold += win
                # Prefer dialogue but always include winnings amount
                line = get_dialogue("town", "gamble_win", None, c)
                shown = None
                if line:
                    try:
                        shown = line.format(win=win, payout=win, gold=win, amount=win)
                    except Exception:
                        shown = line
                if not shown or str(win) not in shown:
                    shown = (shown or "You win!") + f" Payout: {win}g"
                self._emit_dialogue(shown)
            else:
                c.gold = max(0, c.gold - bet)
                # Prefer dialogue but always include loss amount
                line = get_dialogue("town", "gamble_lose", None, c)
                shown = None
                if line:
                    try:
                        shown = line.format(bet=bet, loss=bet, gold=bet, amount=bet)
                    except Exception:
                        shown = line
                if not shown or str(bet) not in shown:
                    shown = (shown or "You lose!") + f" {bet}g"
                self._emit_dialogue(shown)
            self._emit_update_stats()
            self._emit_pause()
            self.s.subphase = ""
            self.s.gamble = {}
            # After result, render town header + summary + menu
            return self._render_town_menu()

        # Range: choose a range and resolve on d20
        if sub == "gamble:range:choose":
            if action == "gamble:back":
                return self._gamble_bet_menu()
            if action and action.startswith("range:"):
                sel = action.split(":", 1)[1]
                ranges = {"1": (1, 5), "2": (6, 10), "3": (11, 15), "4": (16, 20)}
                r = ranges.get(sel)
                if not r:
                    return self._gamble_range_menu()
                # Record and announce player's choice
                g["range_choice"] = r
                self._emit_dialogue(f"You chose {r[0]}-{r[1]} on a d20.")
                try:
                    d = roll_damage("1d20")
                except Exception:
                    import random as _r

                    d = _r.randint(1, 20)
                self._emit_dialogue(f"You roll: {d}")
                bet = int(g.get("bet", 0))
                if r[0] <= d <= r[1]:
                    win = bet * 2
                    c.gold += win
                    line = get_dialogue("town", "gamble_win", None, c)
                    shown = None
                    if line:
                        try:
                            shown = line.format(
                                win=win, payout=win, gold=win, amount=win
                            )
                        except Exception:
                            shown = line
                    if not shown or str(win) not in shown:
                        shown = (shown or "You win!") + f" Payout: {win}g"
                    self._emit_dialogue(shown)
                else:
                    c.gold = max(0, c.gold - bet)
                    line = get_dialogue("town", "gamble_lose", None, c)
                    shown = None
                    if line:
                        try:
                            shown = line.format(bet=bet, loss=bet, gold=bet, amount=bet)
                        except Exception:
                            shown = line
                    if not shown or str(bet) not in shown:
                        shown = (shown or "You lose!") + f" {bet}g"
                    self._emit_dialogue(shown)
                self._emit_update_stats()
                self._emit_pause()
                self.s.subphase = ""
                self.s.gamble = {}
                return self._render_town_menu()

        # default
        return self._gamble_start()

    def _gamble_bet_menu(self) -> List[Event]:
        c = self.s.character
        g = self.s.gamble
        self.s.subphase = "gamble:bet"
        # Reset text screen on stage change (mirrors CLI clear)
        self._emit_clear()
        bet = int(g.get("bet", 0))
        self._emit_dialogue(
            (
                get_dialogue("town", "current_bet", None, c) or "Current bet: {bet}g"
            ).format(bet=bet)
        )
        self._emit_menu(
            [
                ("bet:+5", "+5"),
                ("bet:+10", "+10"),
                ("bet:+50", "+50"),
                ("bet:+100", "+100"),
                ("bet:ok", "OK"),
                ("bet:back", "Back"),
            ]
        )
        self._emit_state()
        return self._flush()

    def _gamble_exact_choose_die(self) -> List[Event]:
        c = self.s.character
        self.s.subphase = "gamble:exact:die"
        self._emit_clear()
        self._emit_dialogue(
            get_dialogue("town", "choose_die", None, c) or "Choose die:"
        )
        self._emit_menu(
            [
                ("exact:d20", "1) D20"),
                ("exact:d10", "2) D10"),
                ("exact:d6", "3) D6"),
                ("gamble:back", "4) Back"),
            ]
        )
        self._emit_state()
        return self._flush()

    def _gamble_range_menu(self) -> List[Event]:
        c = self.s.character
        self.s.subphase = "gamble:range:choose"
        self._emit_clear()
        self._emit_dialogue(
            get_dialogue("town", "choose_range", None, c) or "Choose a range (d20):"
        )
        self._emit_menu(
            [
                ("range:1", "1) 1-5"),
                ("range:2", "2) 6-10"),
                ("range:3", "3) 11-15"),
                ("range:4", "4) 16-20"),
                ("gamble:back", "5) Back"),
            ]
        )
        self._emit_state()
        return self._flush()

    def _gamble_invalid(self) -> List[Event]:
        c = self.s.character
        # Refine invalid messaging per subphase
        sub = self.s.subphase or ""
        if sub == "gamble:bet":
            self._emit_dialogue(
                get_dialogue("town", "invalid_bet", None, c) or "Invalid bet."
            )
        elif sub == "gamble:exact:guess":
            sides = int(self.s.gamble.get("die_sides", 20))
            line = get_dialogue("town", "pick_number", None, c)
            try:
                msg = (line or "Pick a number between 1 and {sides}.").format(
                    sides=sides
                )
            except Exception:
                msg = f"Pick a number between 1 and {sides}."
            self._emit_dialogue(msg)
        else:
            self._emit_dialogue("Invalid input.")
        # Re-show the appropriate prompt/menu instead of bouncing back to start
        if sub == "gamble:bet":
            return self._gamble_bet_menu()
        if sub == "gamble:exact:guess":
            sides = int(self.s.gamble.get("die_sides", 20))
            self._emit_clear()
            menu = [(f"guess:{i}", f"{i}") for i in range(1, sides + 1)]
            menu.append(("gamble:back", f"{len(menu)+1}) Back"))
            self._emit_menu(menu)
            self._emit_state()
            return self._flush()
        if sub == "gamble:exact:die":
            return self._gamble_exact_choose_die()
        if sub == "gamble:range:choose":
            return self._gamble_range_menu()
        return self._gamble_start()

    def _remove_curses_menu(self) -> List[Event]:
        c = self.s.character
        cursed = [item for item in c.magic_items if getattr(item, "cursed", False)]
        if not cursed:
            self._emit_dialogue("You have no cursed items.")
            # Show town header + summary before presenting town options
            return self._render_town_menu()
        items = [("town", "1) Back")]
        for i, item in enumerate(cursed, 2):
            items.append((f"curse:{i-1}", f"{i}) {item.name}"))
        self._emit_menu(items)
        self._emit_state()
        return self._flush()

    def _quests_menu(self) -> List[Event]:
        c = self.s.character
        from .quests import quest_manager
        from .data_loader import get_dialogue

        # Header
        header = get_dialogue("town", "town_bulletin", None, c)
        self._emit_dialogue(header or "Town Bulletin: \n=== Side Quests ===")
        # Body
        qs = list(getattr(c, "side_quests", []) or [])
        if not qs:
            none = get_dialogue("town", "town_bulletin", "none_available", c)
            self._emit_dialogue(none or "You have no active side quests.")
        else:
            lead = get_dialogue("town", "quest_menu_options", None, c)
            self._emit_dialogue(lead or "Current side quests:")
            for q in qs:
                try:
                    desc = q.get("desc", q.get("description", ""))
                    reward = q.get("reward", 0)
                    status = "Done" if q.get("completed") else "Active"
                    self._emit_dialogue(f"- {desc} - Reward: {reward}g ({status})")
                except Exception:
                    self._emit_dialogue(f"- {q}")
        # Menu
        self._emit_menu(
            [("quests:new", "1) Ask for New Side Quests"), ("town", "2) Back")]
        )
        self._emit_state()
        return self._flush()

    def _flush(self) -> List[Event]:
        out = list(self.s.buffer)
        self.s.buffer.clear()
        return out
