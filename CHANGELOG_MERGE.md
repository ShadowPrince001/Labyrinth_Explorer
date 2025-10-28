# Backend Mechanics Merge: Changelog & Test Notes

This document summarizes the backend-only mechanics migration applied to `Labyrinth_Explorer-main`, aligning combat, checks, and systems with the updated rules while keeping all UI text, layout, and styling unchanged.

## Files edited

- game/combat.py
  - Switched core rolls to 5d4 (initiative, attacks, examine, charm, divine, run).
  - Damage formula: weapon die + ceil(STR/2) + buffs; damaged weapon halves output.
  - Armor Class: 10 + ceil(CON/2) + armor (damaged armor halves its AC).
  - Summon creature: uses 5d4 roll; hooks to companion logic preserved.
  - UI strings/messages intentionally unchanged.

- game/engine.py
  - Creation: attributes via 5d4; HP = 3*CON + 3d6; starting gold = 20d6 + ceil(CHA/1.5)d6, plus a low-HP bonus of +5d6 (HP < 50), +7d6 (HP < 40), +10d6 (HP < 30), or +15d6 (HP < 25) — highest matching tier only.
  - Dungeon utility checks: Divine and Listen use 5d4-based rolls.
  - Combat actions: Divine, Charm, Run, Examine converted to 5d4 with updated thresholds.
  - Monster attack rolls: 5d4; messaging preserved.
  - Revival: implemented wisdom-based revival on defeat (5d4 + WIS vs 15 + 5*death_count). Success → -2 to all stats (min 3), set HP=1, return to town. Failure → permanent death (main menu). Death count tracked on the Character.

- game/traps.py
  - Dodge checks now 5d4 + ceil(Dex/2) for both print and event-returning flows.
  - ability_bonus redefined as ceil(stat/2).

- game/entities.py
  - Added minimal fields for new flows: `death_count`, `examine_used_this_turn`, `attribute_training`.
  - Updated serialization with safe defaults for backward compatibility.
  - XP progression updated to per-level increments of 50 (total XP to level L is 50*(L-1)*L/2). Level-ups grant 1 unspent stat point; spending a point on Constitution adds +5 max HP.

- game/quests.py
  - Added `QuestManager` for side quests with generation, progression, and auto turn-in on monster kills.
  - Engine victory flow integrates quest checks and rewards.

## Behavior summary

- All d20 checks in combat and exploration replaced with 5d4, preserving text output. Fumbles occur on the minimum possible roll (e.g., 5 on 5d4), applying self-damage.
- Damage and AC follow the new math rules; damaged gear reduces effectiveness.
- Character creation produces HP and Gold per the updated formulas (including CHA-scaled dice and tiered low-HP bonus), with existing narration.
- On defeat, a revival attempt may return you to town at 1 HP with stat penalties, else permanent death.
- Trap dodges use 5d4 + ceil(Dex/2). Town Rest and Pray also use 5d4-based checks.
 - Town and dungeon utilities now render on clean pages with a pause + Continue: Listen, Open Chest, Divine, Rest, Healer, Eat, Tavern, Pray, Sleep, and all combat-side utility actions (Charm, Run, Examine, Victory, Revival). Layout unchanged; text cleared before result pages, with appropriate dialogue fallbacks.

## Smoke test

1) Compile key files to ensure syntax is clean:

```powershell
python -m py_compile "game\\engine.py"
python -m py_compile "game\\combat.py"
python -m py_compile "game\\traps.py"
python -m py_compile "game\\entities.py"
```

2) New game creation:
- Assign seven 5d4 attribute rolls.
- Confirm HP line shows: `Base HP: 3*CON + 3d6 = total`.
- Confirm Gold line shows: `Base Gold: 20d6 + bonus = total`.

3) Traps:
- Enter the labyrinth until a trap triggers.
- Check `Dodge roll: <5d4 + ceil(Dex/2)> vs DC` and that HP/poison effects apply.

4) Combat actions:
- Use Divine, Charm, Run, Examine; watch 5d4-based roll displays and outcomes.
- Observe monster attacks and damage; gear damage messages may appear occasionally.

5) Revival:
- Intentionally die to trigger revival.
- On success: stats -2 (min 3), HP set to 1, returned to town.
- On fail: permanent death (back to main menu).

## Notes

- UI text intentionally left as-is (some messages still mention d20 terminology).
- Companion summoning remains simplified in engine; a richer table exists in `companion.py` if you want to extend it later.
- Town Rest/Pray checks have been migrated to 5d4. UI strings were minimally updated to remove d20 wording outside of gambling; layout and styling unchanged.

## Recent UX gating enhancements

- Inventory
  - Equip weapon: shows result on a clean page, Pause + Continue returns to Inventory.
  - Equip armor: same Pause + Continue gating added.
  - Unequip weapon/armor: now Pause + Continue instead of jumping back immediately.
  - Potions list keeps existing pause behavior.

- Level Up
  - After the final stat is allocated, the game clears the screen and shows a completion message with a Pause + Continue back to Town (no layout changes).

- Companion
  - Healing your companion now shows a clean result with Pause + Continue back to the Companion menu.

- Quests
  - Asking for new quests or hitting the 3-quest capacity now shows a clean message with Pause + Continue back to the Quests menu.

These match the previously introduced clear-screen + Continue gating used across combat, dungeon utilities, town services, and shop flows, keeping UI structure intact while improving pacing and readability.

## Dragon victory condition

- The Dragon can now appear in three ways:
  - As the 50th monster you encounter (forced spawn).
  - As the monster on Depth 5 (forced spawn at that depth).
  - Randomly via standard wander chance (as defined in data/monsters.json).
- Defeating the Dragon triggers a clean end-game victory screen with Pause + Continue, then an epilogue and return to the main menu. Dialogues use configurable fallbacks when not present.

## Monster stat model update

- Monsters now use base stats directly from `data/monsters.json` (no automatic depth-based scaling of HP/AC/DEX/STR).
- Existing room gold and reward logic remain unchanged; encounter difficulty is governed by the JSON data and encounter weighting.
