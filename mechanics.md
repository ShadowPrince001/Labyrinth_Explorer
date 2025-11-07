# Game Mechanics (Comprehensive)

Code‑accurate mechanics (updated 2025‑11‑07). All formulas and systems extracted directly from `game/engine.py`, `game/entities.py`, `game/quests.py`, `game/shop.py`, `game/companion.py`, and related modules. Dice notation XdY means roll X Y‑sided dice and sum.

## Character Creation

- Difficulty determines the dice used for each attribute roll (7 rolls, one per attribute):
  - Easy: 6d5
  - Normal: 5d5
  - Hard: 4d5
- Attributes: Strength (STR), Dexterity (DEX), Constitution (CON), Intelligence (INT), Wisdom (WIS), Charisma (CHA), Perception (PER). Each rolled value is assigned to one attribute until all 7 are filled.
- Starting HP: Two components to balance predictable toughness (CON scaling) with early variance.
  - Base HP = 3*CON (guarantees each point of CON matters immediately).
  - Bonus = roll(5d4) (range 5–20, avg 12.5) differentiates characters with identical CON.
  - Final formula: Starting HP = 3*CON + roll(5d4)
  - Rationale: 3*CON keeps low-CON builds survivable while still rewarding high CON; 5d4 (multiple dice) narrows variance so extremes (5 or 20) are rarer.
- Starting Gold: Base + CHA bonus + possible low-HP compensation
  - Base = 20d6
  - CHA bonus dice = ceil(CHA / 1.5) d6 (0 if CHA very low)
  - Low-HP bonus (applied after computing HP):
    - If HP < 25 → +15d6
    - Else if HP < 30 → +10d6
    - Else if HP < 40 → +7d6
    - Else if HP < 50 → +5d6
    - Else if HP < 60 → +3d6
  - Total: Gold = roll(20d6) + roll(ceil(CHA / 1.5) d6) + HP_bonus_dice
- Starting equipment: No weapons or armor; visit Shop in town.

## Derived Stats and Core Formulas

- Armor Class (AC)
  - Base: 10 + ceil(CON / 2)
  - Armor: add armor AC (damaged armor counts as half its AC, rounded down); if you have no armor, add +5 (natural protection)
  - Total: AC = 10 + ceil(CON/2) + (ArmorAC or 5)
  - Damaged armor: AC contribution halved (floor).

- Initiative
  - Player: roll(5d4) + DEX
  - Monster: roll(5d4) + monster DEX
  - Ties favor the player (player wins on tie).

- Player Attack Check and Damage
  - To‑hit: roll(5d4) + STR >= enemy AC (after debuffs)
  - Damage on hit: roll(weapon_die) + ceil(STR/2) + damage_buffs, minimum 1
  - Damaged weapon: total damage is halved (minimum 1) before crit multiplier
  - Critical: if the 5d4 roll is 20 (max), damage * 1.5 (ignores block)
  - Fumble: if the 5d4 roll is 5 (min), you injure yourself for roll(1d4) and the attack fails
  - Weapon damage die from JSON; damaged state halves final (pre‑crit) damage.

- Monster Attack and Damage
  - To‑hit: roll(5d4) + floor(STR/2) >= player AC
  - Damage on hit: max(1, roll(monster die) - damage_penalty)
  - Critical: 5d4 = 20 → damage * 1.5
  - Fumble: 5d4 = 5 → self‑injury for max(1, roll(die) − damage_penalty)

- Aim/Defend Zones
  - Aim options: Head (high), Torso (middle), Legs (low).
  - Defender chooses a guard zone. If zones match, the non‑critical attack is blocked.

## Traps

- Occurrence: ~20% chance when entering a room.
- Save: roll(5d4) + ceil(DEX/2) vs trap DC. Success avoids the trap.
- On failure: take trap damage (from its die) and apply effects:
  - gold_dust: lose a fixed amount of gold
  - poison: apply a poison DoT for N turns
  - rust_weapon: flavor only (no permanent damage)
  - dex_down: reduce DEX by an amount

Poison DoT: each of your turns, take max(1, roll(1d4)) for remaining duration; duration decrements each turn.

Typical trap chance on room entry: 20% (see Labyrinth generation). Specific trap effects drawn from `traps.json`.

## Utilities and Special Actions

- Run Away: succeed if roll(5d4) + ceil(DEX/2) > 15 + ceil(monster DEX/2).
- Examine (once per combat): succeed if roll(5d4) + WIS > 25; reveals HP, AC, and DEX (if present). Does not consume your turn.
- Divine Aid (once per depth): roll = roll(5d4) + (WIS - 10) vs 12.
  - On success: deals 4d6 if roll ≥ 16 else 3d6. Monster still takes its turn afterward.
- Charm Monster:
  - Not Dragon‑applicable (Dragon is immune).
  - Success check: roll(5d4) + ceil(CHA/2) >= 20 + floor(difficulty/2)
    - CHA includes any temporary bonuses this combat.
    - difficulty comes from monsters.json for the current monster.
  - On success: monster leaves; you gain 25% of depth‑scaled XP and gold; no loot or quest credit.

## Potions (combat)

- Healing (legacy): heal roll(2d4)
- Intelligence: +1 damage this combat
- Speed: +1 extra attack charge (consumed automatically after a normal Attack)
- Strength: +2 damage this combat
- Protection: +3 AC this combat
- Invisibility: the monster’s next attack automatically misses
- Antidote: clears poison debuff

## Spells (combat)

- Magic Missile: 2d6 damage (reduced by enemy spell resistance if present)
- Fireball: 4d6 damage (reduced by resistance)
- Lightning Bolt: choose power level → Full 6d6 or Half 3d6 (reduced by resistance)
- Freeze: enemy skips its next turn (freeze_turns +1)
- Vulnerability: enemy AC −2 for this combat
- Weakness / Slowness: enemy damage −2 for this combat
- Summon Creature: attempt based on roll(5d4); on success, a companion acts after you each round
- Teleport to Town / Magic Portal: escape combat to town (no rewards)

Note: “Spell resistance” in combat reduces incoming spell damage by a flat amount when present.

## Rewards and Progression

 - Depth multiplier: depth_mult = 1.0 + 0.5*(depth - 1) (Depth 1→1.0, 2→1.5, 3→2.0, 4→2.5, 5→3.0, ...)
 - XP on kill: XP = floor(base_xp * depth_mult) (base_xp from monsters.json)
 - Gold on kill: base_gold = random in gold_range; Gold = floor(base_gold * depth_mult) (fallbacks to monster/room values if missing)
- Charm reward: 25% of the above depth‑scaled rewards; no item drops or quest turn‑ins
- Drops:
  - Potion: min(0.20, 0.05 + 0.01 * diff)
  - Scroll: min(0.20, 0.05 + 0.01 * diff)
  - Magic gear: flat 25% chance (independent of diff). If it drops:
    - 40% Ring (equal chance per ring in `magic_items.json`)
    - 30% Armor (labyrinth‑only entries in `armors.json`, weighted by their `chance`)
    - 30% Weapon (labyrinth‑only entries in `weapons.json`, weighted by their `chance`)
  - Rings bind automatically and immediately apply their attribute effect:
    - Effects with `_bonus` grant a random +2 to +5 to that attribute
    - Effects with `_penalty` apply a random −1 to −3
    - Constitution changes also adjust Max HP by ±5 per attribute point; current HP is clamped to new max
  - Labyrinth gear rewards (weapons/armors) are added to inventory and are unsellable.
- Leveling:
  - Total XP to reach level L: 50 * (L - 1) * L / 2
  - On level‑up: +1 unspent stat point; spending a point increases an attribute by +1 (if you increase CON, max HP +5)
  - Training (separate from level points) detailed below.

## Equipment Wear and Degradation

 - Player weapon: 5% chance to become damaged when your attack is blocked or hits (including crit). No damage chance on a plain miss.
 - Player armor: 5% chance to become damaged when you block an incoming attack or when you get hit.
 - Damaged weapons deal half damage (pre‑crit). Damaged armor provides half of its listed AC.
 - Repair cost at weaponsmith: flat 30g per damaged weapon or armor.

## Rooms, Traps, and Encounters

- Room generation always includes a monster chosen by wander_chance, except:
  - Depth 5 forcibly generates a Dragon room.
  - The engine forces a Dragon on the 50th monster encounter milestone.
- Chests: 25% chance; 10–100 gold; 50% chance to also contain a magic item.
- Traps: see Traps section above; 20% chance on room entry.

Chest Generation:
- Chance: 25% per room (non‑dragon) to spawn a chest.
- Chest contents: 10–100 gold; 50% chance to also include a magic item.

Dragon / Forced Encounters:
- Depth 5 always generates a Dragon room.
- Additionally forced after 50th monster encounter milestone.

Monster Selection respects wander_chance; quests only assigned to monsters with wander_chance > 0.02.

Room Background mapping uses regex/proximity logic (see scene manager) ensuring descriptive shape matches image.

---
## Town Actions (Recovery & Services)

All recovery rolls use roll(5d4) + relevant attribute; success threshold > 25 heals ceil(MaxHP/3).

Actions (cost / attribute used / limits):
- Eat (10g / Charisma / once per visit): Roll, success heals; failure message only. Sets used_eat.
- Drink (Tavern, 10g / Charisma / once per visit): Same heal logic; failure yields flavor text. sets used_tavern.
- Pray (Temple / Wisdom / once per visit): Free; success heals; failure yields faith message. sets used_pray.
- Sleep (Inn / Constitution / once per visit): Free; success heals; failure yields no heal. sets used_sleep.
- Rest (Inn “rest” flow / Constitution / cost 10g): If available, 5d4+CON vs 25 → heal ceil(MaxHP/3).
- Healer (40g): Full heal to max HP and removes debuff_* persistent effects (no roll).
- Remove Curses (10g): Presents list of cursed magic items; selecting removes the curse (no roll) – items become sellable.
- Weaponsmith Repair (30g each): Restores full effectiveness (weapon) or protection (armor).

Utilities reset on death (revival) for next depth attempt.

---
## Training & Attribute Growth

Separate from level-up stat points. Limited training sessions total (cap 7).
 - Cost formula: Cost = 50 * (trained_times + 1).
- Each session: pay cost, +1 chosen attribute.
- Constitution training: also +5 max HP.
- Tracks per-attribute counts in `attribute_training` map.
- After 7 total trainings: further training unavailable.

Level-Up Points: each spent point +1 to chosen attribute (CON adds +5 max HP similarly).

---
## Shop Economy

Buying (UI engine):
- Weapons: pay listed `price`; add to inventory (not auto-equipped except via armor logic); damage die from data.
- Armor: pay `price`; auto-equip newest armor.
- Potions & Spells: pay `cost` (fallback to `price` for potions); grant listed `uses`; Healing potion also increments legacy `potions` count for compatibility.

Selling (Two Implementations):
1. Web Engine Haggle (engine internal):
  - Base price: original shop price (weapons/armor) or nominal 100 for magic items.
  - Offer formula: start at 50% base; apply Charisma tier (>=15 +20%, <=6 −20%); apply random variance * (0.9–1.1); round down; minimum 1.
  - Confirm sale adds gold; equipped or damaged items can’t be sold; cursed items excluded.
2. CLI Appraisal (shop.py):
  - Roll appraisal = 5d4 + CHA.
  - Percent = (roll + CHA) * 0.025.
  - Final price = ceil(original price * percent); minimum 1.
  - Shows detailed line: “Sell roll: R + CHA(C) -> P% of Base = Price”.
  - Confirmation required; cannot sell equipped/damaged items; potions reduce uses.

Repair Differences: Both flows rely on weaponsmith (30g) for damaged equipment before selling; damaged items blocked from sale.

Magic Items: Engine assigns nominal base 100g (if uncursed) for haggle; cursed items must be cleansed (10g) before sale.

---
## Side Quests

Quest Limit: Max 3 active; requesting new when already at 3 yields a denial message.
Generation:
- Candidates: monsters with wander_chance > 0.02 not already targeted.
- Type: 60% kill / 40% collect (collect is flavor; mechanics still goal=1 kill).
- Goal: always 1.
 - Reward Formula: Reward = floor(difficulty * 20 + (1 / max(wander_chance, 0.01)) // 2).
Completion:
- Any kill of target monster completes quest immediately and auto-awards gold, removing quest.
- No manual turn-in step in engine (auto removal); CLI provides turn_in for completed quests.

---
## Revival & Death

On defeat (combat or trap lethal): attempt Wisdom-based revival.
- Track `death_count` increment first.
 - Roll: roll(5d4) + Wisdom.
 - DC: 15 + 5 * death_count.
- Success: all core attributes −1 (min 3); HP set to 1; depth reset deferred (flags `defer_depth_reset` applied on next labyrinth entry); once-per-depth utilities reset.
- Failure: permanent death (return to main menu).
- Post-revival: Room/monster state cleared; must re-enter labyrinth from depth 1.

---
## Companion System

Summoning:
- Spell/utility triggers roll (5d4 base) then apply modifiers: final_roll = raw_roll + INT_mod + CHA_mod with D&D-style mods floor((stat-10)/2).
- Eligible entries: companion table rows where final_roll ≥ min_roll; pick highest tier not exceeding final_roll (random among matches).
- Tiers: Low (min 8, 2d6 damage), Mid (min 12, 3d6), High (min 16, 4d6). AC, STR, HP rolled within entry ranges.

Companion Attack:
- Attack value: d20 + companion STR.
- Hit if > monster AC; damage = max(1, roll(damage_die)).
- Miss: no damage.

Healing Companion:
- Consume one Healing potion use (legacy `potions` or `potion_uses['Healing']`).
- Heal: roll(2d4) HP (min 1), capped at companion max HP.

Naming: Set companion.name freely.

---
## Gambling (Town)

Modes:
- Exact Guess: Choose die (d20, d10, d6); pick exact face; payout defined by UI flow (text feedback only, code handles win state messaging).
- Range Guess: Fixed d20; pick range (1–5, 6–10, 11–15, 16–20). Bet adjusts potential reward (implementation messaging only; payout logic handled in engine state not documented separately here as monetary scaling is textual).

Bet Adjustments: +5 / +10 / +50 / +100 buttons accumulate bet before confirmation.

Invalid inputs re-prompt; back returns to previous menu.

---
## Curses & Removal

Magic items may carry `cursed` flag (loaded from data). Effects block selling; removal menu costs 10g and lists only cursed items.
- Selecting an item (after paying) clears its cursed status making it sellable.
- If none cursed: message and return to town.

---
## Healing & Consumables Summary

Combat Potions: (see Potions section). Town recovery heals use ceil(MaxHP/3) on success.
Healing Potion (legacy quick consume): roll(2d4) player heal; companion heal also 2d4.
Scroll / spell uses tracked; purchase increases counts.

---
## Sell Price Comparison Example

Example weapon base price 80g:
- Web Engine Haggle (CHA 16, variance 1.05): Offer ≈ floor((80*0.5)*1.2*1.05) = floor(50.4) = 50g.
- CLI Appraisal (roll 30, CHA 16): percent = (30+16)*0.025 = 1.15 → ceil(80*1.15)=92g.
Demonstrates appraisal can exceed original price; engine haggle caps implicitly via formula.

---
## Edge Cases & Notes

- Minimum sale value always ≥1g.
- Damaged or equipped gear blocked from sale until repaired/unequipped.
- Cursed items blocked until curse removed (10g).
- Revival penalties cannot reduce attributes below 3.
- Training costs escalate rapidly; consider timing before late-game deaths.
- Depth multiplier applies equally to XP and gold (except charm at 25%).
- Chest item chance independent of combat drops (drops occur only on monster defeat).
- Monster gold fallback order: `mon.gold_reward` then `room.gold_reward` if `gold_range` missing.
- Healing services don’t remove attribute penalties from revival.

---
## Data Sources

All numeric values sourced from JSON under `data/` and logic in Python modules; if JSON changes, formulas here remain valid but numeric ranges (e.g., monster difficulty, gold_range) may shift.

## Notes
See Data Sources section. This document aims for mechanical clarity; flavor text (dialogues) may alter narration but not numbers.

### Reviews (external)
- From the Main Menu choose "Review (Rate /5)".
- You must enter a rating 1–5 (text is optional).
- Submitting creates a new text file in the repository (in `reviews/`) via the GitHub API.
- Reviews aren’t viewable in‑game; open the GitHub repo to see them.
