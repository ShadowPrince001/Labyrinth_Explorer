# Game Mechanics

This document summarizes core game systems, stats, and rules as implemented in the event-driven engine.

## Character Creation

- Difficulty selection:
  - Easy: 6d5 stat rolls
  - Normal: 5d5 stat rolls
  - Hard: 4d5 stat rolls
- Attributes: Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma, Perception.
- HP: Based on Constitution (base) + roll bonuses during creation.
- Gold: Base roll plus Charisma bonus dice and possible low-HP compensations.

## Town Hub

- Actions: Shop, Healer, Tavern, Eat, Temple (Pray), Level Up, Quests, Train, Sleep, Companion, Repair, Remove Curses, Gamble, Inventory, Save.
- Refresh actions (Rest/Eat/Drink/Pray/Sleep) have per-visit limits and stat-gated healing.
- Healer removes debuffs and restores HP for gold.

## Labyrinth

- Depth starts at 1 and increases as you go deeper; rooms are generated per depth.
- Trap checks can occur at entry; chests may contain gold or magic items.
- A special Dragon encounter is forced at every 50th monster encountered.

## Combat

- Turn-based. Player options:
  - Attack: choose aim and equipped weapon.
  - Use Potion: healing or antidote; legacy healing uses scaled `2d2` rolls.
  - Cast Spell: includes offensive, support, or utility effects.
  - Divine: Wisdom-influenced roll can trigger damage from above.
  - Charm: Charisma-influenced roll; on success, foe leaves peacefully.
  - Run: Dexterity-influenced roll versus monster dexterity.
  - Examine: Wisdom roll to reveal stats and a short description.

### Rewards

- On victory (kill):
  - XP = base_xp × depth, where base_xp is from `data/monsters.json`.
  - Gold = base_gold × depth, where base_gold is sampled uniformly from the monster’s `gold_range` in `data/monsters.json`.
  - May trigger side quest turn-ins and random drops (potions, scrolls, magic items).
- On successful charm:
  - XP = 50% × (base_xp × depth)
  - Gold = 50% × (base_gold × depth)
  - No quest progression or random drops.

Notes:
- `room.gold_reward` now mirrors the sampled `base_gold` for that encounter (kept for consistency); empty-room chest gold is unaffected.

### Reward math and comparison

Previous vs current formulas (kill):
- Previous gold formula (per room): base_old = Uniform(5..15) + 2·depth; Gold_old_kill = depth × base_old.
- Current gold formula (per monster): base_new = Uniform(lo..hi) from monsters.json; Gold_new_kill = depth × base_new.
- Charm yields half of the corresponding kill reward (XP and gold).

Dataset stats (from `data/monsters.json`):
- XP base min/avg/max = 10 / 87.10 / 260
- Gold base (json) lo/min = 3, hi/max = 300, avg of means ≈ 80.03

Examples by depth (kill rewards, charm is half of each):
- Depth 1: old gold min/avg/max = 7 / 12.0 / 17; new gold min/avg/max = 3 / 80.0 / 300
- Depth 2: old gold min/avg/max = 18 / 28.0 / 38; new gold min/avg/max = 6 / 160.1 / 600
- Depth 3: old gold min/avg/max = 33 / 48.0 / 63; new gold min/avg/max = 9 / 240.1 / 900
- Depth 4: old gold min/avg/max = 52 / 72.0 / 92; new gold min/avg/max = 12 / 320.1 / 1200
- Depth 5: old gold min/avg/max = 75 / 100.0 / 125; new gold min/avg/max = 15 / 400.2 / 1500

XP comparison (kill):
- Old (pre-scaling): min/avg/max = 10 / 87.1 / 260
- New (depth-scaled):
  - Depth 2 → 20 / 174.2 / 520
  - Depth 3 → 30 / 261.3 / 780
  - Depth 4 → 40 / 348.4 / 1040
  - Depth 5 → 50 / 435.5 / 1300

### Verified Mechanics & Corrections

- Examine:
  - Wisdom check (5d4 + WIS > 25). Shows HP/AC (and DEX when available).
  - After Examine, play returns to the player menu; the monster does not immediately attack.
  - Use at most once per combat (tracked in engine state).
- Divine:
  - Wisdom-influenced roll: 5d4 + (WIS - 10). On success, deals 3d6 or 4d6 damage depending on roll; on failure, no effect.
  - In both success and failure cases, the monster takes its turn afterward.
- Dragon (from data/monsters.json):
  - HP 135, AC 31, STR 22, DEX 18, Damage 8d7, XP 250, gold 200–300.
  - This encounter is intentionally extreme and may require high stats, gear, items, and favorable RNG.

## Spells & Effects (Highlights)

- Lightning Bolt / Fireball: Damage spells with dice scaling.
- Freeze: Skip monster's next turn.
- Vulnerability: Reduce monster AC during this combat.
- Heal: Restore player HP.
- Teleport to Town / Magic Portal: Leave combat and return to town.

## Utilities

- Divine and Listen are once per depth and reveal hints about the next room's monster or sound.
- Examine during combat reveals monster AC/HP and a description when available.

## Items

- Weapons/Armors from shop; Magic items may drop and can be inspected from dungeon actions.
- Potions include Healing and Antidote; some items apply bonuses or penalties.

## Quests

- Side quests can be accepted in town; kills may progress and automatically turn-in with rewards when conditions are met.

## Notes

- All dialogue can be authored in `data/dialogues.json` where present.
- See `project_overview.md` for runtime architecture and file layout.
