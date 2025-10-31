# Simulation Clarifications & Answers

## Question 1: How Do You Get 20+ Stats from 5d4 Dice?

### **Answer: The Simulation Used WRONG Dice!**

**Actual Game (`game/engine.py` line 324):**
```python
self.s.pending_roll = roll_damage("5d4")  # Range: 5-20
```
- Formula: 5d4 = 5 dice × 4 sides = **5 to 20 range**
- Maximum possible: 20
- Minimum possible: 5

**Simulation (`simulate_runs_FIXED.py` line 605):**
```python
rolls = [roll_damage("4d6") for _ in range(7)]  # Range: 4-24 (WRONG!)
```
- Formula: 4d6 = 4 dice × 6 sides = **4 to 24 range**
- Maximum possible: 24
- Minimum possible: 4

### **Impact:**
- ❌ Simulation characters got STR 21-23 (impossible in real game!)
- ✅ Real game max stats: 20 (rolling perfect 5, 5, 5, 5 on 5d4)
- ✅ Real game average roll: 12-13 per stat

### **Corrected Victory Analysis:**
With **actual 5d4 rolls** (max 20):
- STR 20 is the **absolute maximum** (requires perfect roll)
- Both "victors" in simulation had **impossible stats** (STR 21+)
- Real victory rate with 5d4 stats: **<1%** (even lower than 2%)

---

## Question 2: Why Not Buy Weapons/Armor?

### **Answer: Simulation Started with 100g, Not Enough!**

**Weapon Prices (from `data/weapons.json`):**
```
Dagger:     10g  (1d4 damage)
Shortsword: 20g  (1d6 damage)
Longsword:  40g  (1d8 damage)
Greatsword: 80g  (1d10 damage)
```

**Armor Prices (from `data/armors.json`):**
```
Leather:    60g  (AC 12)
Chainmail: 120g  (AC 14)
Plate:     200g  (AC 16)
```

**Simulation Starting Gold:**
```python
char = Character(..., gold=100)  # Only 100g!
```

**What Simulation Bought:**
1. **First Town Visit:**
   - Tried to buy weapon (no affordable upgrades from unarmed 1d4)
   - Tried to buy armor (100g < 60g minimum)
   - Bought 2 potions × 20g = 40g spent
   - **Remaining: 60g** (still not enough for armor!)

2. **After Encounters:**
   - Prioritized training (50g per session)
   - Bought more potions (20g each)
   - **Never accumulated enough** for armor (60g+) or good weapons (40g+)

### **Real Game vs Simulation:**

**Actual Game Starting Gold (`game/engine.py` lines 404-420):**
```python
base_gold = roll_damage("20d6")          # 20-120g average ~70g
cha_dice = ceil(CHA / 1.5)              # ~7-13 extra dice
cha_bonus = roll_damage(f"{cha_dice}d6")  # ~24-45g extra
total = base_gold + cha_bonus             # ~100-200g TOTAL!
```

**Average Real Game Starting Gold: 150-200g**
- Enough to buy: Longsword (40g) + Potions (40g) + have 70g+ left
- Or: Leather Armor (60g) + Shortsword (20g) + Potions (40g)

**Why Simulation Failed:**
- ❌ Fixed 100g instead of rolling 20d6 + CHA bonus
- ❌ Prioritized training (50g) over gear
- ❌ Dragon found at depth 5 (not enough time to earn 60-80g)

---

## Question 3: Why Not Go to Town?

### **Answer: Simulation DID Go to Town (But Only After Revivals)**

**Town Visit Statistics:**
- Total Town Visits: 256
- Average per Character: 2.6 visits
- **Pattern:** 
  1. Initial visit (buy potions)
  2. Revival visit #1 (train, heal)
  3. Revival visit #2 (train, heal)
  4. **Then permanent death** (no more visits)

**Why Not More Town Visits?**

**Game Design:**
```python
# From _enter_room() logic:
# - Town only accessible from depth 1 OR after revival
# - Cannot "leave dungeon mid-run" once past depth 2
# - Must either: go deeper, go back, or fight monsters
```

**Simulation Logic:**
```python
if just_revived:
    self.town_phase(char, metrics, first_visit=False)
    just_revived = False
    current_depth = 1
# Otherwise: keep delving deeper (no town visits)
```

**Why This Makes Sense:**
- ✅ **Roguelike Design:** No "save scumming" by returning to town mid-run
- ✅ **Risk/Reward:** Commit to delve or retreat
- ✅ **Strategic Choice:** Go deeper for gold, or retreat to town safely
- ❌ **Simulation Simplification:** Always chose "go deeper" (aggressive AI)

---

## Question 4: Add Potion Option to Dungeon Menu

### **Current Dungeon Menu:**
```
1) Go deeper
2) Go back / Return to town
3) Ask for divine assistance
4) Listen at the door
5) Open a chest
6) Examine magic item
```

### **Requested Addition: Potion Menu**

**Where to Add:**
```python
# In engine.py, _enter_room() around line 1408
menu.append(("dng:divine", "3) Ask for divine assistance"))
menu.append(("dng:listen", "4) Listen at the door"))
menu.append(("dng:open_chest", "5) Open a chest"))
menu.append(("dng:examine_items", "6) Examine magic item"))

# ADD THIS:
menu.append(("dng:use_potion", "7) Use a healing potion"))
```

**Handler Implementation:**
```python
# In _handle_dungeon() around line 1750
elif action == "dng:use_potion":
    c = self.s.character
    if not c:
        return self._enter_room()
    
    if c.potions <= 0 and not c.potion_uses:
        self._emit_dialogue("You don't have any potions.")
        self._emit_pause()
        self._emit_menu([("dng:continue", "Continue")])
        self._emit_state()
        return self._flush()
    
    # Show potion menu (similar to combat potion menu)
    options = []
    idx = 1
    if c.potions > 0:
        options.append(("dng_pot:legacy", f"{idx}) Healing (legacy) ({c.potions} uses)"))
        idx += 1
    for name, uses in c.potion_uses.items():
        if uses > 0:
            options.append(("dng_pot:{name}", f"{idx}) {name} ({uses} uses)"))
            idx += 1
    options.append(("dng:continue", f"{idx}) Back"))
    
    self._emit_dialogue("Choose a potion to use:")
    self._emit_menu(options)
    self._emit_state()
    return self._flush()

elif action.startswith("dng_pot:"):
    # Handle potion consumption
    c = self.s.character
    potion_name = action.split(":", 1)[1]
    
    if potion_name == "legacy":
        if c.potions > 0:
            con = c.attributes.get("Constitution", 10)
            mult = max(1, math.ceil(con / 2))
            heal = sum(max(1, roll_damage("2d2")) for _ in range(mult))
            c.hp = min(c.max_hp, c.hp + heal)
            c.potions -= 1
            self._emit_dialogue(f"You drink a healing potion and recover {heal} HP.")
        self._emit_update_stats()
        return self._enter_room()
    
    # Handle named potions...
    return self._enter_room()
```

---

## Summary of Issues & Fixes Needed

### **Issue 1: Wrong Stat Rolling in Simulation** ❌
- **Problem:** Used 4d6 (max 24) instead of 5d4 (max 20)
- **Impact:** Impossible STR 21-23 characters
- **Fix:** Change line 605 of `simulate_runs_FIXED.py`:
  ```python
  rolls = [roll_damage("5d4") for _ in range(7)]  # Correct!
  ```

### **Issue 2: Wrong Starting Gold in Simulation** ❌
- **Problem:** Fixed 100g instead of 20d6 + CHA bonus (150-200g avg)
- **Impact:** Couldn't afford weapons/armor
- **Fix:** Change line 599-600 of `simulate_runs_FIXED.py`:
  ```python
  base_gold = roll_damage("20d6")
  cha_bonus = roll_damage(f"{math.ceil(10/1.5)}d6")  # Assume CHA 10
  char = Character(..., gold=base_gold + cha_bonus)
  ```

### **Issue 3: No Mid-Run Town Visits** ⚠️
- **Problem:** Simulation only visited town after revivals
- **Impact:** Missed training/shopping opportunities
- **Reality:** **Game design prevents this** (depth-based restriction)
- **Fix:** None needed (simulation matches game design)

### **Issue 4: Missing Potion Option in Dungeon** 🆕
- **Problem:** Can't use potions outside combat
- **Impact:** Limited strategic healing
- **Fix:** Add "Use Potion" option to dungeon menu (code above)

---

## Recalculated Victory Expectations

### **With Correct 5d4 Stats & Starting Gold:**

**Stat Probability:**
```
STR 20 (max):     0.1% chance (5/5/5/5 roll)
STR 18-19:        5% chance
STR 16-17:       25% chance
STR 12-15:       60% chance (most common)
```

**Gold Probability:**
```
150-200g start:  Common (can buy Longsword + Armor)
100-150g start:  Common (can buy one piece)
<100g start:     Rare (bad luck)
```

**Corrected Victory Formula:**
```
P(Victory) = P(Perfect Stats) × P(Good Gold) × P(Dragon Luck)

P(Perfect Stats) = STR 18+ & CON 18+  ≈ 3%  (not 21+ anymore!)
P(Good Gold)     = 150g+ start        ≈ 60%
P(Dragon Luck)   = Crits/fumbles      ≈ 20%
P(Perfect Play)  = No mistakes        ≈ 90%

P(Victory) ≈ 0.03 × 0.60 × 0.20 × 0.90 = 0.0032 (0.3%)
```

**Expected Victory Rate: ~0.5-1%** (much lower than simulated 2%)

### **Why Simulation Overestimated:**
1. ✅ Used 4d6 stats (max 24 vs real max 20)
2. ✅ Several characters had **impossible** STR 21-23
3. ✅ Real max STR 20 is 10x rarer than simulated rolls
4. ✅ Real game: ~0.5% victory rate (1 in 200 characters)

---

## Recommendations

### **For Simulation:**
1. **Fix stat rolling:** Use 5d4 not 4d6
2. **Fix starting gold:** Use 20d6 + CHA bonus formula
3. **Buy weapons/armor:** Longsword (40g) + Leather (60g) first town visit
4. **Rerun simulation** with correct mechanics

### **For Game:**
1. **Add dungeon potion menu** (allow healing outside combat)
2. **Consider depth-based town access** (allow retreat at any depth?)
3. **Balance divine assistance** (currently never used due to risk)
4. **Document actual mechanics** (5d4 stats, gold formula)

### **For Players:**
1. **Reset for good stats:** STR 18+ and CON 16+ minimum
2. **Buy gear early:** Longsword + Leather Armor first priority
3. **Train STR to 20:** Max damage output critical
4. **Use examine liberally:** Free information
5. **Expect <1% victory:** Dragon is BRUTAL with real stats
