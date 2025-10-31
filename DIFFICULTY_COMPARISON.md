# Difficulty Comparison: Side-by-Side

## Character Creation Comparison

### Scenario: Creating Three Characters

```
╔════════════════════════════════════════════════════════════════════╗
║                    EASY DIFFICULTY (6d5)                           ║
╠════════════════════════════════════════════════════════════════════╣
║ Strength:      [18] ████████████████████                          ║
║ Dexterity:     [16] ████████████████                              ║
║ Constitution:  [20] ████████████████████████                      ║
║ Intelligence:  [15] ███████████████                               ║
║ Wisdom:        [19] ███████████████████                           ║
║ Charisma:      [17] █████████████████                             ║
║ Perception:    [21] █████████████████████                         ║
║                                                                    ║
║ Total Stats: 126 | HP: 70 | AC: 30 | Gold: 180g                  ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║                   NORMAL DIFFICULTY (5d5)                          ║
╠════════════════════════════════════════════════════════════════════╣
║ Strength:      [15] ███████████████                               ║
║ Dexterity:     [13] █████████████                                 ║
║ Constitution:  [16] ████████████████                              ║
║ Intelligence:  [12] ████████████                                  ║
║ Wisdom:        [17] █████████████████                             ║
║ Charisma:      [14] ██████████████                                ║
║ Perception:    [18] ██████████████████                            ║
║                                                                    ║
║ Total Stats: 105 | HP: 56 | AC: 28 | Gold: 150g                  ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║                    HARD DIFFICULTY (4d5)                           ║
╠════════════════════════════════════════════════════════════════════╣
║ Strength:      [12] ████████████                                  ║
║ Dexterity:     [10] ██████████                                    ║
║ Constitution:  [14] ██████████████                                ║
║ Intelligence:  [ 9] █████████                                     ║
║ Wisdom:        [13] █████████████                                 ║
║ Charisma:      [11] ███████████                                   ║
║ Perception:    [15] ███████████████                               ║
║                                                                    ║
║ Total Stats: 84  | HP: 45 | AC: 26 | Gold: 130g                  ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## Combat Scenario: Fighting a Goblin (HP: 20, AC: 15, STR: 12)

### Round 1: Initiative

```
┌─────────────────────────────────────────────────────────────┐
│ EASY (DEX 16)    vs Goblin (DEX 10): Easy goes first! ✓    │
│ NORMAL (DEX 13)  vs Goblin (DEX 10): Normal goes first! ✓  │
│ HARD (DEX 10)    vs Goblin (DEX 10): 50/50 coin flip...    │
└─────────────────────────────────────────────────────────────┘
```

### Round 1: Player Attack

```
EASY Character (STR 18):
  Roll: d20 = 8
  Attack: 8 + 18 = 26 vs AC 15 → HIT! ✓
  Damage: 1d8 + 18 = 23 damage
  Result: Goblin dies instantly! ☠️

NORMAL Character (STR 15):
  Roll: d20 = 8  
  Attack: 8 + 15 = 23 vs AC 15 → HIT! ✓
  Damage: 1d8 + 15 = 19 damage
  Result: Goblin dies! ☠️

HARD Character (STR 12):
  Roll: d20 = 8
  Attack: 8 + 12 = 20 vs AC 15 → HIT! ✓
  Damage: 1d8 + 12 = 16 damage
  Result: Goblin dies! ☠️
```

**Analysis:** Against weak enemies, all difficulties can win. Let's try a tougher fight...

---

## Combat Scenario: Fighting a Troll (HP: 80, AC: 25, STR: 22, DEX: 15)

### Round 1: Initiative

```
┌─────────────────────────────────────────────────────────────┐
│ EASY (DEX 16)    vs Troll (DEX 15): Easy goes first! ✓     │
│ NORMAL (DEX 13)  vs Troll (DEX 15): Troll goes first! ✗    │
│ HARD (DEX 10)    vs Troll (DEX 15): Troll goes first! ✗    │
└─────────────────────────────────────────────────────────────┘
```

### Round 1: Player Attack

```
EASY Character (STR 18):
  Roll: d20 = 12
  Attack: 12 + 18 = 30 vs AC 25 → HIT! ✓
  Damage: 1d10 + 18 = 24 damage
  Troll HP: 80 → 56
  Status: Troll wounded, fight continues...

NORMAL Character (STR 15):
  Roll: d20 = 12
  Attack: 12 + 15 = 27 vs AC 25 → HIT! ✓
  Damage: 1d10 + 15 = 20 damage
  Troll HP: 80 → 60
  Status: Troll wounded, fight continues...

HARD Character (STR 12):
  Roll: d20 = 12
  Attack: 12 + 12 = 24 vs AC 25 → MISS! ✗
  Damage: 0
  Troll HP: 80 (unchanged)
  Status: No damage dealt!
```

### Round 2: Troll Attack (Normal & Hard took hits because Troll went first)

```
EASY: Troll attacks AC 30
  Roll: d20 = 14
  Attack: 14 + 11 (STR/2) = 25 vs AC 30 → MISS! ✗
  Damage: 0
  Easy HP: 70 (unchanged) 😊

NORMAL: Troll attacks AC 28
  Roll: d20 = 14
  Attack: 14 + 11 = 25 vs AC 28 → MISS! ✗
  Damage: 0
  Normal HP: 56 (unchanged) 😊

HARD: Troll attacks AC 26
  Roll: d20 = 14
  Attack: 14 + 11 = 25 vs AC 26 → MISS! ✗
  Damage: 0
  Hard HP: 45 (unchanged) 😊
```

*(Note: Troll got lucky this round and missed all three)*

### Round 3: Different Troll Roll

```
Troll rolls: d20 = 18
Attack: 18 + 11 = 29

EASY (AC 30):   29 vs 30 → MISS! ✗      (HP: 70)    ✓ Safe
NORMAL (AC 28): 29 vs 28 → HIT! ✓       (HP: 56→36) ⚠️ Hurt
HARD (AC 26):   29 vs 26 → HIT! ✓       (HP: 45→25) 💀 Critical
```

**Troll Damage:** 2d8 + 11 = 20 damage average

### Combat Summary After 5 Rounds

```
╔════════════════════════════════════════════════════════════╗
║                      EASY SURVIVOR                         ║
╠════════════════════════════════════════════════════════════╣
║ HP: 70 → 55 (took 1 hit)                                  ║
║ Hits Landed: 4 out of 5 (80%)                             ║
║ Damage Dealt: 96 → Troll Dead! ✓                          ║
║ Potions Used: 0                                            ║
║ Status: VICTORY - Easy Win                                 ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║                     NORMAL SURVIVOR                        ║
╠════════════════════════════════════════════════════════════╣
║ HP: 56 → 16 (took 2 hits)                                 ║
║ Hits Landed: 3 out of 5 (60%)                             ║
║ Damage Dealt: 60 → Troll Still Alive (20 HP left)         ║
║ Potions Used: 1 (emergency heal)                           ║
║ Status: SURVIVING - Close Call                            ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║                      HARD CASUALTY                         ║
╠════════════════════════════════════════════════════════════╣
║ HP: 45 → 0 (took 3 hits + critical)                       ║
║ Hits Landed: 2 out of 5 (40%)                             ║
║ Damage Dealt: 40 → Troll Still Alive (40 HP left)         ║
║ Potions Used: 2 (tried to survive)                         ║
║ Status: DEAD - Teleported to Town 💀                      ║
╚════════════════════════════════════════════════════════════╝
```

---

## Skill Check Scenario: Using Divine Vision

**Situation:** Player wants to see what monster is in the next room.  
**Requirement:** 5d4 + Wisdom > 25

```
┌──────────────────────────────────────────────────────────────┐
│ EASY Character (WIS 19):                                     │
│   Roll: 5d4 = 12 (average)                                   │
│   Total: 12 + 19 = 31                                        │
│   Result: 31 > 25 → SUCCESS! ✓                              │
│   Vision: "You see a Dragon ahead..."                        │
│   Decision: Flee to town! Smart choice.                      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ NORMAL Character (WIS 17):                                   │
│   Roll: 5d4 = 12 (average)                                   │
│   Total: 12 + 17 = 29                                        │
│   Result: 29 > 25 → SUCCESS! ✓                              │
│   Vision: "You see a Dragon ahead..."                        │
│   Decision: Flee to town! Smart choice.                      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ HARD Character (WIS 13):                                     │
│   Roll: 5d4 = 12 (average)                                   │
│   Total: 12 + 13 = 25                                        │
│   Result: 25 > 25 → FAIL! ✗ (needs GREATER than 25)         │
│   Vision: "You can't see anything..."                        │
│   Decision: Walk into Dragon fight blind! 💀                │
└──────────────────────────────────────────────────────────────┘
```

**Outcome:**
- Easy & Normal: Avoided deadly fight, saved resources
- Hard: Walked into Dragon, died instantly, lost progress

---

## Economic Scenario: Shopping at Town Market

**Item Prices:**
- Plate Armor: 300g
- Health Potion: 20g
- Weapon Upgrade: 100g

### Starting Gold Comparison

```
╔════════════════════════════════════════════════════════════╗
║ EASY: 180 gold                                             ║
╠════════════════════════════════════════════════════════════╣
║ Purchase 1: Chain Mail (150g) → 30g remaining             ║
║ Purchase 2: Health Potion (20g) → 10g remaining           ║
║ Purchase 3: (Save for later)                               ║
║                                                            ║
║ Equipment: Chain Mail + Potions ✓                          ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║ NORMAL: 150 gold                                           ║
╠════════════════════════════════════════════════════════════╣
║ Purchase 1: Weapon Upgrade (100g) → 50g remaining         ║
║ Purchase 2: Leather Armor (50g) → 0g remaining            ║
║ Purchase 3: Cannot afford potions! ✗                       ║
║                                                            ║
║ Equipment: Leather + Good Weapon (no potions) ⚠️          ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║ HARD: 130 gold                                             ║
╠════════════════════════════════════════════════════════════╣
║ Purchase 1: Leather Armor (50g) → 80g remaining           ║
║ Purchase 2: Basic Weapon (50g) → 30g remaining            ║
║ Purchase 3: 1 Health Potion (20g) → 10g remaining         ║
║                                                            ║
║ Equipment: Leather + Basic Weapon + 1 Potion ⚠️           ║
╚════════════════════════════════════════════════════════════╝
```

---

## Revival Scenario: Chapel of Resurrection

**Character dies at Depth 10 for the 2nd time**  
**Revival DC:** 15 + (2 × 5) = 25  
**Roll:** 5d4 + Wisdom > 25

```
┌──────────────────────────────────────────────────────────────┐
│ EASY Character (WIS 19):                                     │
│   Roll: 5d4 = 11 (slightly below average)                    │
│   Total: 11 + 19 = 30                                        │
│   Result: 30 > 25 → SUCCESS! ✓                              │
│   "You feel the divine power surging through you..."         │
│   Revived! Can continue adventuring. 😊                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ NORMAL Character (WIS 17):                                   │
│   Roll: 5d4 = 11 (slightly below average)                    │
│   Total: 11 + 17 = 28                                        │
│   Result: 28 > 25 → SUCCESS! ✓                              │
│   "The ritual barely succeeds... you return to life."        │
│   Revived! But it was close. 😰                             │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ HARD Character (WIS 13):                                     │
│   Roll: 5d4 = 11 (slightly below average)                    │
│   Total: 11 + 13 = 24                                        │
│   Result: 24 > 25 → FAIL! ✗                                 │
│   "The divine spark fades... you cannot be revived."         │
│   PERMANENT DEATH - Character deleted. 💀                   │
└──────────────────────────────────────────────────────────────┘
```

**Impact:**
- Easy: Can reliably revive 2-3 times
- Normal: Can usually revive twice, risky 3rd time
- Hard: 2nd revival is 50/50, 3rd revival nearly impossible

---

## Progression Timeline: First 10 Rooms

### Easy Difficulty

```
Room 1: Goblin → Easy kill (1 round)
Room 2: Trap → Detected (PER 21) → Avoided
Room 3: Treasure → Found bonus gold (+50g)
Room 4: Orc → Killed (3 rounds, no damage taken)
Room 5: Empty → Used Divine (saw next enemy)
Room 6: Wolf → Fled successfully (DEX 16)
Room 7: Chest → Looted (+30g, +1 potion)
Room 8: Skeleton → Killed (2 rounds, 5 damage taken)
Room 9: Empty → Healed with potion
Room 10: Miniboss → Killed (6 rounds, 20 damage taken)

Status: HP: 50/70 | Gold: 260g | Potions: 3 | Depth: 10
Ready for more! 💪
```

### Normal Difficulty

```
Room 1: Goblin → Killed (2 rounds)
Room 2: Trap → Detected (PER 18) → Avoided
Room 3: Treasure → Found (+30g)
Room 4: Orc → Killed (5 rounds, 15 damage taken)
Room 5: Empty → Used Divine (failed roll)
Room 6: Wolf → Fought (3 rounds, 20 damage taken)
Room 7: Chest → Looted (+20g)
Room 8: Skeleton → Killed (4 rounds, 15 damage taken)
Room 9: Empty → Used potion (+25 HP)
Room 10: Miniboss → Fled (too dangerous)

Status: HP: 31/56 | Gold: 200g | Potions: 1 | Depth: 9
Need to go back to town for healing. 🏥
```

### Hard Difficulty

```
Room 1: Goblin → Killed (3 rounds)
Room 2: Trap → Missed (PER 15) → Took 10 damage!
Room 3: Treasure → Found (+15g)
Room 4: Orc → Fled (DEX check passed)
Room 5: Empty → Used Divine (failed)
Room 6: Wolf → Fought (6 rounds, 25 damage taken)
Room 7: Chest → Looted (+10g)
Room 8: Skeleton → Died in combat 💀

Status: Teleported to town, HP restored
Cost: 50g revival fee | Gold: 25g | Potions: 0 | Depth: 1
Struggling to progress... 😰
```

---

## Long-Term Progression: After 100 Rooms

```
╔════════════════════════════════════════════════════════════╗
║                    EASY - DEPTH 25                         ║
╠════════════════════════════════════════════════════════════╣
║ Deaths: 3 (all revived successfully)                       ║
║ Gold: 2,500g (fully equipped)                              ║
║ Equipment: Plate Armor +2, Legendary Sword, Ring +3        ║
║ Level: 8                                                   ║
║ Status: Dominating endgame content                         ║
║ Achievement: "Deep Delver" unlocked! 🏆                   ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║                   NORMAL - DEPTH 18                        ║
╠════════════════════════════════════════════════════════════╣
║ Deaths: 6 (4 revived, 2 failed)                            ║
║ Gold: 1,200g (decent equipment)                            ║
║ Equipment: Chain Mail +1, Good Sword, Ring +1              ║
║ Level: 6                                                   ║
║ Status: Progressing steadily, some setbacks                ║
║ Achievement: "Seasoned Explorer" unlocked! 🥈             ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║                    HARD - DEPTH 10                         ║
╠════════════════════════════════════════════════════════════╣
║ Deaths: 12 (5 revived, 7 failed = 7 full restarts!)       ║
║ Gold: 300g (basic equipment)                               ║
║ Equipment: Leather Armor, Basic Sword, No Ring             ║
║ Level: 4                                                   ║
║ Status: Repeatedly dying, slow progress                    ║
║ Achievement: "Stubborn Survivor" unlocked! 🥉             ║
╚════════════════════════════════════════════════════════════╝
```

---

## Stat Comparison: Visual Breakdown

```
STRENGTH (Attack Bonus)
Easy    [6-30]:  ██████████████████████████████ (Avg: 18)
Normal  [5-25]:  █████████████████████████      (Avg: 15)
Hard    [4-20]:  ████████████████████           (Avg: 12)

CONSTITUTION (HP & AC)
Easy    [6-30]:  ██████████████████████████████ (Avg: 18 → 60 HP)
Normal  [5-25]:  █████████████████████████      (Avg: 15 → 48 HP)
Hard    [4-20]:  ████████████████████           (Avg: 12 → 36 HP)

WISDOM (Divine, Revival, Examine)
Easy    [6-30]:  ██████████████████████████████ (Avg: 18 → 85% success)
Normal  [5-25]:  █████████████████████████      (Avg: 15 → 70% success)
Hard    [4-20]:  ████████████████████           (Avg: 12 → 50% success)

CHARISMA (Starting Gold)
Easy    [6-30]:  ██████████████████████████████ (Avg: 18 → 170g)
Normal  [5-25]:  █████████████████████████      (Avg: 15 → 150g)
Hard    [4-20]:  ████████████████████           (Avg: 12 → 130g)
```

---

## Final Verdict: Choose Your Experience

```
┌──────────────────────────────────────────────────────────────┐
│ 🟢 EASY: "Hero's Journey"                                   │
├──────────────────────────────────────────────────────────────┤
│ • Feel powerful and capable                                  │
│ • Enjoy the story and exploration                            │
│ • Reach endgame content reliably                             │
│ • Perfect for: New players, casual play, story focus         │
│ • Experience: Action RPG                                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🟡 NORMAL: "Balanced Challenge"                             │
├──────────────────────────────────────────────────────────────┤
│ • Strategic decisions matter                                 │
│ • Tense but fair combat                                      │
│ • Meaningful resource management                             │
│ • Perfect for: Most players, intended experience             │
│ • Experience: Traditional dungeon crawler                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🔴 HARD: "Survival Nightmare"                               │
├──────────────────────────────────────────────────────────────┤
│ • Every decision is life or death                            │
│ • Frequent permadeaths expected                              │
│ • Requires perfect play and luck                             │
│ • Perfect for: Veterans, challenge seekers, roguelike fans   │
│ • Experience: Hardcore survival roguelike                    │
└──────────────────────────────────────────────────────────────┘
```

---

**Side-by-Side Comparison v1.0**  
**Last Updated:** October 31, 2025
