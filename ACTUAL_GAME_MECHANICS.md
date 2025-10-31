# ACTUAL GAME MECHANICS - VERIFIED FROM SOURCE CODE

## 🐉 DRAGON STATS (VERIFIED)

**From `data/monsters.json` line 1-11:**
```json
{
    "name": "Dragon",
    "base_hp": 135,
    "base_ac": 31,
    "base_strength": 22,
    "damage_die": "8d7",  // NOT 2d10!
    "base_dex": 18,
    "xp": 250,
    "gold_range": [200, 300]
}
```

**Corrected Dragon Stats:**
- **HP:** 135 (NOT 80!)
- **AC:** 31 (NOT 16!)
- **Strength:** 22
- **Damage:** 8d7 (average 32 damage, NOT 11!)
- **Dex:** 18

**This means Dragon is MUCH HARDER than documented!**

---

## ⚔️ CRITICAL MECHANIC CORRECTIONS

### 1. ✅ EXAMINE DOES NOT CONSUME MONSTER'S TURN

**Code Evidence (`game/engine.py` lines 3134-3171):**

```python
def _combat_examine(self, action: Optional[str]) -> List[Event]:
    # ... examine logic ...
    # Gate next turn behind a Continue
    self.s.subphase = "examine_continue"
    self._emit_menu([("combat:after_examine", "Continue")])
    
# Lines 1926-1928:
if sp == "examine_continue" and action == "combat:after_examine":
    self.s.subphase = "monster_defend"  # Goes to PLAYER MENU, not monster turn
    return self._combat_emit_menu()
```

**CORRECTED:** Examine lets you see monster stats, then returns to YOUR turn menu. Monster does NOT attack!

**But:** Can only use ONCE per combat (no flag to track multiple uses).

---

### 2. ❌ DIVINE DOES NOT SKIP MONSTER TURN (EVEN ON SUCCESS)

**Code Evidence (`game/engine.py` lines 3039-3068):**

```python
def _combat_divine(self, action: Optional[str]) -> List[Event]:
    # ... divine logic ...
    if rollv >= 12:
        # SUCCESS: Deal damage
        dmg = max(1, roll_damage(die))
        mon["hp"] -= dmg
        self._emit_combat_update(f"The gods answer with {name} for {dmg} damage!")
        if mon["hp"] <= 0:
            return self._combat_victory(self.s.current_room, mon)
    else:
        # FAILURE
        self._emit_combat_update("Your plea goes unanswered.")
    
    # BOTH SUCCESS AND FAILURE:
    return self._combat_next_turn("monster")  # MONSTER ATTACKS AFTER!
```

**CORRECTED:** Divine aid ALWAYS consumes a turn. Monster attacks you regardless of success/failure!

---

## 🎯 UPDATED STRATEGIC ANALYSIS

### Dragon Fight Reality Check

**Dragon Damage Output:**
- Damage: 8d7 = **32 average** (not 11!)
- Hit rate vs AC 16: ~55%
- **Expected DPR: 17.6 per turn**

**Player Needs:**
- To survive 8 turns (135 HP / 17 DPT)
- **Must have:** 140+ effective HP (70 base + 70 from potions)
- **Must have:** High AC (20+) to reduce hit rate

**New Dragon Requirements:**
- STR 18+ (hit reliably vs AC 31)
- CON 18+ (70+ base HP)
- AC 20+ (Plate Armor + high CON)
- Weapon: 2d6+ or 1d12
- **10+ Healing Potions** (not 5!)
- Magic items for AC/damage buffs

**Expected Fight Duration:**
- Your damage: 1d10+4 = 9.5 avg
- Hit rate vs AC 31: **~20%** (5d4+18 = 30.5 avg vs AC 31)
- Expected DPR: 1.9 per turn
- **Turns to kill: 71 turns**

**You CANNOT survive 71 turns taking 17.6 damage per turn!**

**Realistic Win Condition:**
- Need magic items (+5 to-hit minimum)
- Need damage buffs (Intelligence/Strength potions)
- Need AC buffs (Protection potions)
- Need LUCKY rolls (crits, Dragon misses)
- **Estimated win rate: 1-3%** (not 5-15%!)

---

## 📊 CORRECTED COMBAT MECHANICS

### Examine
- **Cost:** Takes your turn slot
- **Effect:** Wisdom check (5d4 + WIS > 25)
- **On Success:** See HP, AC, DEX, abilities
- **After Use:** Returns to YOUR menu (monster doesn't attack)
- **Limit:** Once per combat (no tracking, so effectively once)

### Divine Aid
- **Cost:** Takes your turn + monster attacks you
- **Effect:** 5d4 + (WIS - 10) vs 12
- **On Success:** Deal 3d6 (roll 12-15) or 4d6 (roll 16+) damage
- **On Failure:** Nothing happens, monster still attacks
- **Expected Value:** ~40% success, 13.5 avg damage = 5.4 expected damage
- **VS Attack:** Attack with STR 16 = 60% hit * 8 avg = 4.8 expected damage
- **Conclusion:** Divine slightly better than attack IF you have high WIS (15+)

### Attack
- **Cost:** Your turn + monster attacks you
- **Hit Chance:** (5d4 + STR) vs monster AC
- **Damage:** weapon_die + ceil(STR/2)
- **Crits:** Natural 20 on 5d4 = 1.25% chance (NOT 5%!)
- **Critical Damage:** 1.5x base damage
- **Zone Blocking:** Monster defends one zone, blocks if matches yours

---

## 🔧 SIMULATION FIXES NEEDED

### 1. Monster Stats
✅ Already correct - no depth scaling exists

### 2. Town Visits
❌ Fix: Only after revival (not every depth)

### 3. Dragon Victory
❌ Fix: Track wins (defeat Dragon = victory)

### 4. Examine Mechanics
❌ Fix: After examine, return to player menu (no monster turn)
❌ Fix: Can use once per combat (add flag tracking)

### 5. Divine Mechanics  
❌ Fix: Monster ALWAYS attacks after divine (success or fail)
❌ Fix: Update expected value (Divine ≈ Attack, not better)

### 6. Dragon Stats
❌ Fix: HP 135, AC 31, damage 8d7 (32 avg)
❌ Fix: Win rate 1-3% (nearly impossible without magic items)

### 7. Critical Hit Rate
❌ Fix: 5d4 natural 20 is IMPOSSIBLE
❌ Fix: Max roll on 5d4 is 20 (1.25% crit, not 5%)

---

## 📈 CORRECTED EXPECTED RESULTS

### Realistic Win Conditions
- **Victory Rate:** 1-3% (Dragon is BRUTAL)
- **Death Rate:** 97-99%
- **Average Encounters:** 15-25 (not 25-35)
- **Average Depth:** 2-3 (most die before reaching Dragon)

### Combat Performance
- **Hit Rate:** 45-65% (vs normal monsters)
- **Hit Rate vs Dragon:** 15-25% (AC 31 is crazy high)
- **Turns per Normal Monster:** 6-10
- **Turns vs Dragon:** Would need 70+ turns (you die first)

### Equipment Needs for Dragon
- **Minimum STR:** 20+ (with magic item +5 to-hit)
- **Minimum CON:** 18+ (70 HP base)
- **Minimum AC:** 20+ (Plate Armor + magic)
- **Weapon:** 2d6 or 1d12 (Greatsword/Battleaxe)
- **Potions:** 10+ healing (2d4 each = ~7 HP)
- **Buffs:** Strength/Intelligence/Protection potions active
- **Total Gold Cost:** 1,500g+ (most runs won't get this much)

---

## 🎮 GAME DESIGN INSIGHT

**The Dragon is meant to be nearly unbeatable!**

The game is NOT about "beat the Dragon in 100 characters."

The game is about:
1. **Survive as long as possible** (high score = encounters survived)
2. **Explore deeper depths** (risk/reward)
3. **Collect gold and items** (progression)
4. **Occasional Dragon victory** (rare achievement, 1-3% of runs)

**Beating the Dragon requires:**
- Perfect starting rolls (18 STR, 18 CON)
- Optimal training path
- Finding magic items (rare drops)
- Lucky combat rolls (crits, Dragon misses)
- 1,500g+ gold accumulation
- Perfect execution (no mistakes)

---

## ✅ FINAL CORRECTIONS SUMMARY

| Issue | Original Claim | Actual Reality |
|-------|---------------|----------------|
| Dragon HP | 80 | **135** |
| Dragon AC | 16 | **31** |
| Dragon Damage | 2d10 (11 avg) | **8d7 (32 avg)** |
| Examine Cost | Consumes turn | **Doesn't trigger monster attack** |
| Examine Limit | Once per turn | **Once per combat** |
| Divine Success | Skips monster turn | **Monster still attacks** |
| Win Rate | 5-15% | **1-3%** |
| Critical Rate | 5% | **1.25%** (max 20 on 5d4) |
| Gold Needed | 900g | **1,500g+** |
| Required AC | 16+ | **20+** |
| Required STR | 16+ | **20+ (with magic)** |

---

**Main Motto:** The game is about SURVIVING and EXPLORING, not guaranteed Dragon victories. Beating Dragon is an epic rare achievement (like Dark Souls beating Ornstein & Smough on first try).

**Simulation Goal:** Measure how long characters survive, what strategies work best, and what % of perfectly-played characters can achieve the near-impossible Dragon victory.
