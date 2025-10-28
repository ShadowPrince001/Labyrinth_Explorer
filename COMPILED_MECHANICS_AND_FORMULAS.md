# Labyrinth Explorer — Compiled Mechanics & Formulas

This file gathers every dice rule, formula, and mechanic implemented or documented across the project into one place. Use it as a single reference when balancing, modding, or writing tests.

Sources (key files):
- `COMPLETE_MECHANICS_FORMULAS.md`
- `DICE_USAGE_REFERENCE.md`
- `BACKGROUND_SYSTEM_COMPLETE.md`
- `README.md`
- `game/dice.py`, `game/combat.py`, `game/engine.py`, `game/traps.py`, `game/entities.py`

---

## Quick contract (what this doc covers)
- Inputs: character attributes, monster data, weapon/armor data (from `data/*.json` and `game/entities.py`).
- Outputs: hit / miss outcomes, damage numbers, HP changes, revival outcomes, gold/xp rewards, potion/spell effects.
- Error modes: damaged equipment (reduced effect), failed revival (permanent death), out-of-range indices when selecting weapons (fallbacks used).

---

## Dice system (core)

- Dice notation: NdM (N = number of dice, M = sides). Implemented in `game/dice.py`.
  - parse_die("NdM") → (N, M)
  - roll("NdM") → sum of N rolls of 1..M using random.randint(1, M)
  - roll_d20() → random.randint(1, 20) (kept for shop/gamble flavor; main mechanics use 5d4)
  - roll_damage(die) → wrapper for roll(die)

- Primary in-game dice conventions (used pervasively):
  - Attribute generation: 5d4 for each attribute (range 5–20, average 12.5)
  - Attack & many skill checks: 5d4 + attribute modifier
  - HP bonus at creation: 3d6
  - Starting gold: 20d6 + bonus (bonus depends on Charisma/HP)
  - Healing potion: 2d4
  - Rest heal / Healer: 2d6
  - Spell damages: 2d6 (magic missile), 3d6/6d6 (lightning bolt), 4d6 (fireball), 4d6 (heal spell in some places), variable from `data/*.json`
  - Poison DoT: 1d4 per turn

Note: 5d4 is used instead of a d20 across combat and checks. That yields a minimum roll of 5, maximum 20, mean 12.5 — fewer extreme fails than d20.

---

## Attributes and character creation

- Attributes: Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma, Perception.
- Generation: roll 5d4 per attribute, assign values during creation (implemented in `game/engine.py`).
- HP at creation:
  - Base HP = 3 × Constitution
  - HP bonus = roll `3d6`
  - Starting max_hp = Base HP + HP bonus
  - Current HP set to max_hp at creation

- Starting gold:
  - Base gold = roll `20d6`
  - Charisma bonus = roll `ceil(CHA/1.5)d6`
  - Low-HP bonus (apply highest matching tier): if HP < 50 add `5d6`; if HP < 40 add `7d6`; if HP < 30 add `10d6`; if HP < 25 add `15d6`
  - Final = 20d6 + ceil(CHA/1.5)d6 + optional low-HP tier bonus

---

## Armor Class (AC)

- Player AC calculation (implemented in `game/combat.py` / `game/engine.py`):
  - Base AC: 10 + ceil(Constitution / 2) (some summaries also present simplified base_ac = CON//2 + armor)
  - Equipped armor AC added (if armor damaged, add armor_class // 2)
  - Potions/temporary buffs: add `ac_bonus` to AC for duration

- Monster AC: read from `data/monsters.json` as `armor_class` and used directly; some docs list ranges used per index.

Examples:
- Player with CON 14, no armor: AC = 10 + ceil(14/2) = 10 + 7 = 17

---

## Attack roll and hit determination

- Attack roll (player):
  - attack_roll = roll_damage("5d4") + Strength
  - If attack_die (the raw 5d4 total) equals maximum (20): treated as a critical hit (special handling)

- Attack roll (monster):
  - monster_attack_roll = roll_damage("5d4") + floor(monster_strength / 2)

- Hit condition: attack_roll >= target_AC ⇒ hit

Edge behaviors:
- Perfect defense (zones): if defender chose same zone as attacker (head/mid/legs), non-critical attacks are blocked.
- Critical hit: when the raw 5d4 roll = maximum (20) (or legacy code checks for attack_die == 20), damage multiplied by 1.5 (rounded int).
- Fumbles: if the raw attack die equals the minimum possible value (e.g., 5 on 5d4), the attacker fumbles and injures themself (1d4 damage for players; monsters apply their damage die minus penalties). This mirrors the "least number means fumble" rule.

Implementation references: `game/combat.py` and `game/engine.py` (`_combat_attack_resolve`, `player_turn`, `monster_turn`).

---

## Damage calculation

- Player damage formula (implemented in many places):
  - base_damage = roll_damage(weapon.damage_die) + ceil(Strength / 2) + buffs.get("damage_bonus", 0)
  - if weapon.damaged: base_damage = max(1, base_damage // 2)
  - final_damage = max(1, base_damage)
  - critical damage = int(final_damage * 1.5)

- Monster damage:
  - base_damage = roll_damage(monster.damage_die) - enemy_debuffs.get("damage_penalty", 0)
  - final damage = max(1, base_damage)
  - criticals multiply by 1.5 similarly

Examples:
- Player with Strength 14 (ceil(14/2) = 7), weapon 1d8, roll 5 on 1d8:
  - base_damage = 5 + 7 = 12 → final 12 (before crit)

---

## Equipment degradation

- Weapon damage chance on successful hit: chance = monster.armor_class * 0.001 (0.1% per AC point)
  - If chance triggers, `weapon.damaged = True` (weapon deals half damage thereafter).

- Armor damage chance on monster hit: chance = monster.strength * 0.001 (0.1% per monster strength point)
  - Damaged armor provides half its `armor_class`.

Source: multiple spots in `game/combat.py` and `game/engine.py` where chance is calculated and applied.

---

## Criticals & natural failures (special cases)

- Critical success:
  - When the raw attack die equals the maximum possible value (20 on 5d4), code treats it as a critical hit (1.5× damage). See `_combat_attack_resolve` and `player_turn`.

- Natural failure/hurt yourself: present as above — on a minimum roll, the attacker suffers self-damage.

---

## Initiative

- Initiative roll: roll_damage("5d4") + Dexterity (player) vs roll_damage("5d4") + monster.dexterity (monster)
- Higher or equal wins (player goes first on tie) — see `initiative_order` and `_combat_roll_initiative`.

---

## Spells and potions (effects and dice)

- Potions (common):
  - Healing: 2d4 HP restored (combat & out-of-combat)
  - Strength potion: +2 damage bonus
  - Intelligence potion: +1 damage bonus
  - Speed potion: +1 extra attack charge
  - Protection potion: +3 AC bonus
  - Invisibility potion: next monster attack misses
  - Antidote: remove poison
  - Implementation: `use_potion` in `game/combat.py` and `_combat_use_potion` in `game/engine.py`.

- Spells (examples):
  - Magic Missile: roll_damage("2d6")
  - Lightning Bolt: roll_damage("6d6") full or `3d6` half-power (player chooses)
  - Fireball: roll_damage("4d6")
  - Summon Creature: uses roll_damage("5d4") to determine summon success
  - Divine Assistance: roll_damage("5d4") + (Wisdom - 10) vs 12; success deals 3d6 or 4d6 depending on roll (engine)

Spell resist / damage reduction: enemy_debuffs may contain `spell_resistance` to reduce damage (see `cast_spell`).

---

## Revival, death & resurrection rules

- On death: `attempt_revival` implements revival logic (in `game/combat.py`):
  - character.death_count increments each death
  - base_chance = max(5, 60 - (death_count * 10)) percent (e.g., first death 50–60% depending on initial doc variances; code uses 60 - 10*death_count)
  - wisdom_roll = roll_damage("5d4") + Wisdom
  - difficulty = 15 + (death_count * 5)
  - Revival succeeds if wisdom_roll >= difficulty OR luck_roll(1..100) <= base_chance
  - On success: all stats reduced by 2 (min 3), hp = 1, player returned to town
  - On failure: permanent death (game over for that character)

Notes: The doc `COMPLETE_MECHANICS_FORMULAS.md` contains a table by death count; code implements the same math with base_chance/difficulty formulas as above.

---

## Experience & leveling

- XP required per level up: level_transition_xp(level) = level × 50 (so Level 1→2 = 50, 2→3 = 100, 3→4 = 150)
- Cumulative XP to reach target_level = sum_{L=2..target_level} (L-1) × 50 (helper in `Character.get_xp_for_level`).
- Level up reward: +1 unspent stat point (spent interactively to increase an attribute by 1). If Constitution increases, max HP increases by +5.

Example cumulative XP:
- To reach Level 3: 50 + 100 = 150 XP

---

## Economy: gold, selling and costs

- Chest / combat gold: gold reward read from room/monster data (see `generate_room` usage in `game/engine.py` and `data/monsters.json`).
- Equipment selling: selling_price = base_price * min(1.0, charisma * 4 / 100)
  - Example: CHA 10 → 40% of base price.
- Town costs (implemented in `game/engine.py` flows):
  - Healer full heal: 20g
  - Meals: 10g (in engine eat flow uses 10g heal 10 HP), tavern 5g with probabilistic heal 5–10 HP
  - Training costs: 50 * (trained_times + 1)

Notes on dice in town systems:
- Shop haggling (selling): now uses a 5d4 appraisal roll in `game/shop.py` combined with Charisma to compute the offer, aligning with the core 5d4 system.
- Gambling mini-game: uses d20 ranges explicitly in `game/engine.py`.

---

## Traps and saves

- Trap resolution (`game/traps.py`):
  - Dodge/save: roll_damage("5d4") + ceil(Dexterity / 2) to align with the 5d4 core system
  - Trap DC compared against total roll; on failure, damage = roll_damage(trap.damage) and effects applied.
  - Poison effect places persistent debuff `debuff_poison` with duration, handled by `apply_poison_dot` which deals `1d4` per turn.

---

## Quests

- Quest reward formula (doc & engine interplay): reward = difficulty * 20 + (1.0 / max(wander_chance, 0.01)) // 2 (approximate documented formula).
- Quests are primarily kill quests, auto-complete on kill; gold reward only (no XP from quests by default).

---

## Special mechanics and combat flow details

- Aimed attacks & defended zones: attacker chooses a zone (high/middle/low) and defender chooses a zone; matching zones cause a perfect block. (See `choose_aim_zone`, `choose_defend_zone`, `_normalize_zone_input`.)
- Examine monster: `5d4 + Wisdom` vs 25 reveals HP, AC and abilities (does not consume turn, once per turn).
- Run away: `5d4 + ceil(Dex/2)` vs (15 + ceil(monster_dex/2)).
- Divine assistance: `5d4 + (Wisdom - 10)` vs 12 to deliver a spell (3d6/4d6) as described.

---

## Probabilities & balance notes (from docs)

- 5d4 distribution: range 5–20, mean 12.5. This reduces frequency of extreme failures vs d20.
- Example win-rate notes (from `COMPLETE_MECHANICS_FORMULAS.md`): STR 15 vs AC 24 ~ 94.8% hit; STR 20 vs AC 30 ~ 88.1% (these were computed in analysis and included in docs).

Practical takeaways:
- Strength increases both hit chance and flat damage through ceil(STR/2) bonus.
- Training and leveling can overcome monster AC scaling, but permanent death amplifies unlucky streaks.

---

## Code references (where each formula lives)

- Dice engine: `game/dice.py` — parse_die, roll, roll_damage, roll_d20
- Combat math & flows: `game/combat.py` — revival, compute_armor_class, examine_monster, player_turn, monster_turn, charm_monster, run_away, cast_spell
- Event-driven engine: `game/engine.py` — attribute rolling (5d4), HP/gold calculation (3d6, 20d6), initiative, combat orchestration, potion/spell wrappers
- Traps: `game/traps.py` — trap DCs, dice for damage/effects, resolution and event-friendly wrappers
- Entities and data classes: `game/entities.py` — Character, Monster, Weapon, Armor dataclasses and helper methods (gain_xp, summary, to_dict/from_dict)

---

## Worked examples

1) Example: Player Attack
- Player STR = 14 → strength bonus used in damage = ceil(14/2) = 7
- Weapon = 1d8, roll = 5
- Attack die (5d4) = 14 → attack_roll = 14 + 14 = 28
- Target AC = 18 → Hit. Damage = roll(1d8)=5 + 7 = 12

2) Example: Divine revival on first death
- death_count becomes 1 → base_chance = max(5, 60 - (1*10)) = 50%
- Wisdom = 12, wisdom_roll = roll(5d4) + 12; difficulty = 15 + (1*5) = 20
- Revival succeeds if wisdom_roll >= 20 OR luck_roll(1..100) <= 50

---

## How to use this compiled file

- Read it when designing new monsters, tuning weapon/armor values or adjusting global RNG.
- If you change dice types in `game/dice.py`, update this file to reflect the new notation and consequences.
- For testing: write unit tests that sample the dice distributions (roll many times) and assert empirical means/variance to verify RNG behavior.

---

## Next steps / suggested improvements

- Consider documenting and exporting the expected probability tables for key comparisons (STR+5d4 vs AC ranges) as CSV for balancing.
- Add unit tests for dice functions, revival edge cases, and equipment degradation probability.

---

## Completion / verification

I compiled the formulas and code references into this single file by extracting from the project docs and code. If you'd like, I can:
- also generate a CSV of probabilities for typical attribute/AC combinations,
- or add unit tests that assert the documented formulas produce the same numeric outcomes as the code.

---

References: see the top of this file for exact source files included.
