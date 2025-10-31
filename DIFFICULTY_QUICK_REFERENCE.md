# Quick Reference: Difficulty Impact Tables

## At-a-Glance Comparison

### Stat Ranges

| Attribute     | Easy (6d5) | Normal (5d5) | Hard (4d5) |
|--------------|------------|--------------|------------|
| Minimum      | 6          | 5            | 4          |
| Maximum      | 30         | 25           | 20         |
| Average      | 18         | 15           | 12         |
| Total (7 stats) | ~126    | ~105         | ~84        |

---

## Core Mechanics Impact

### HP (Hit Points)

| Difficulty | CON Range | Base HP (3×CON) | With 3d6 | Average Total | Min | Max |
|------------|-----------|-----------------|----------|---------------|-----|-----|
| Easy       | 6-30      | 18-90           | +3-18    | **60**        | 21  | 108 |
| Normal     | 5-25      | 15-75           | +3-18    | **48**        | 18  | 93  |
| Hard       | 4-20      | 12-60           | +3-18    | **36**        | 15  | 78  |

**Difference:** Easy has **67% more HP** than Hard

---

### Armor Class (AC)

| Difficulty | CON | No Armor | Leather (AC 3) | Chain (AC 5) | Plate (AC 7) |
|------------|-----|----------|----------------|--------------|--------------|
| Easy       | 30  | 30       | 33             | 35           | **37**       |
| Easy       | 18  | 24       | 27             | 29           | 31           |
| Normal     | 25  | 28       | 31             | 33           | **35**       |
| Normal     | 15  | 23       | 26             | 28           | 30           |
| Hard       | 20  | 25       | 28             | 30           | **32**       |
| Hard       | 12  | 21       | 24             | 26           | 28           |

**Formula:** AC = 10 + ceil(CON/2) + Armor_AC + Bonuses

**Difference:** Easy can achieve **AC 37** vs Hard's **AC 32** (5 points = ~25% fewer hits)

---

### Attack Bonus

| Difficulty | STR | Attack Bonus | Hit % vs AC 15 | Hit % vs AC 25 | Hit % vs AC 30 |
|------------|-----|--------------|----------------|----------------|----------------|
| Easy       | 30  | +30          | 100%           | 65%            | 40%            |
| Easy       | 18  | +18          | 95%            | 45%            | 20%            |
| Normal     | 25  | +25          | 100%           | 60%            | 35%            |
| Normal     | 15  | +15          | 80%            | 35%            | 10%            |
| Hard       | 20  | +20          | 100%           | 50%            | 25%            |
| Hard       | 12  | +12          | 65%            | 25%            | 5%             |

**Formula:** Attack = d20 + STR vs Enemy_AC

**Difference:** Against AC 25 enemy, Easy (STR 18) hits **80% more often** than Hard (STR 12)

---

### Starting Gold

| Difficulty | CHA | Base (20d6) | CHA Bonus | Low-HP Bonus* | Total Range |
|------------|-----|-------------|-----------|---------------|-------------|
| Easy       | 30  | 70          | ~70       | 0-52          | **140-192** |
| Easy       | 18  | 70          | ~42       | 0-52          | **112-164** |
| Normal     | 25  | 70          | ~58       | 0-52          | **128-180** |
| Normal     | 15  | 70          | ~35       | 0-52          | **105-157** |
| Hard       | 20  | 70          | ~47       | 0-52          | **117-169** |
| Hard       | 12  | 70          | ~28       | 15-52         | **113-150** |

*Low-HP Bonus: 15d6 if HP<25, 10d6 if HP<30, 7d6 if HP<40, 5d6 if HP<50

**Formula:** Gold = 20d6 + ceil(CHA/1.5)×d6 + Low_HP_Bonus

**Difference:** Easy characters start with **20-40% more gold** on average

---

## Skill Check Success Rates

**Important:** All skill checks use **5d4 base roll** (NOT affected by difficulty). Only the stat modifier differs.

### Divine Vision / Examine Monster (Wisdom)
**Target:** 5d4 + WIS > 25

| WIS  | Easy | Normal | Hard | Roll Range | Success % |
|------|------|--------|------|------------|-----------|
| 30   | ✓    | -      | -    | 34-50      | 100%      |
| 25   | ✓    | ✓      | -    | 29-45      | 100%      |
| 20   | ✓    | ✓      | ✓    | 24-40      | 95%       |
| 18   | ✓    | ✓    | -    | 22-38      | 85%       |
| 15   | ✓    | ✓      | ✓    | 19-35      | 70%       |
| 12   | ✓    | ✓      | ✓    | 16-32      | 50%       |
| 10   | -    | ✓      | -    | 14-30      | 35%       |
| 6    | ✓    | -      | -    | 10-26      | 10%       |
| 4    | -    | -      | ✓    | 8-24       | 0%        |

**Average Success:** Easy 75%, Normal 60%, Hard 45%

---

### Listen (Perception)
**Target:** 5d4 + PER > 25

| PER  | Easy | Normal | Hard | Roll Range | Success % |
|------|------|--------|------|------------|-----------|
| 30   | ✓    | -      | -    | 34-50      | 100%      |
| 25   | ✓    | ✓      | -    | 29-45      | 100%      |
| 20   | ✓    | ✓      | ✓    | 24-40      | 95%       |
| 18   | ✓    | ✓      | -    | 22-38      | 85%       |
| 15   | ✓    | ✓      | ✓    | 19-35      | 70%       |
| 12   | ✓    | ✓      | ✓    | 16-32      | 50%       |
| 10   | -    | ✓      | -    | 14-30      | 35%       |
| 6    | ✓    | -      | -    | 10-26      | 10%       |

**Average Success:** Easy 75%, Normal 60%, Hard 45%

---

### Chapel Revival (Wisdom)
**Target:** 5d4 + WIS > DC (15 + revivals × 5)

| WIS | 1st Death (DC 20) | 2nd Death (DC 25) | 3rd Death (DC 30) | 4th Death (DC 35) |
|-----|-------------------|-------------------|-------------------|-------------------|
| 30  | 100%              | 100%              | 100%              | 85%               |
| 25  | 100%              | 100%              | 95%               | 60%               |
| 20  | 100%              | 95%               | 70%               | 35%               |
| 18  | 100%              | 85%               | 55%               | 25%               |
| 15  | 95%               | 70%               | 35%               | 10%               |
| 12  | 85%               | 50%               | 20%               | 0%                |
| 10  | 75%               | 35%               | 10%               | 0%                |
| 6   | 55%               | 10%               | 0%                | 0%                |

**Typical Case:**
- Easy (WIS 18): 3 revivals reliable, 4th possible
- Normal (WIS 15): 2 revivals reliable, 3rd risky  
- Hard (WIS 12): 1 revival reliable, 2nd 50/50, 3rd unlikely

---

### Flee Combat (Dexterity)
**Target:** 5d4 + Player_DEX vs 5d4 + Monster_DEX

#### vs DEX 15 Monster

| Player DEX | Easy | Normal | Hard | Success % |
|------------|------|--------|------|-----------|
| 30         | ✓    | -      | -    | 100%      |
| 25         | ✓    | ✓      | -    | 95%       |
| 20         | ✓    | ✓      | ✓    | 85%       |
| 18         | ✓    | ✓      | -    | 80%       |
| 15         | ✓    | ✓      | ✓    | 70%       |
| 12         | ✓    | ✓      | ✓    | 60%       |
| 10         | -    | ✓      | -    | 50%       |
| 6          | ✓    | -      | -    | 35%       |

#### vs DEX 25 Monster

| Player DEX | Easy | Normal | Hard | Success % |
|------------|------|--------|------|-----------|
| 30         | ✓    | -      | -    | 85%       |
| 25         | ✓    | ✓      | -    | 70%       |
| 20         | ✓    | ✓      | ✓    | 60%       |
| 18         | ✓    | ✓      | -    | 55%       |
| 15         | ✓    | ✓      | ✓    | 45%       |
| 12         | ✓    | ✓      | ✓    | 35%       |

**Average Success:** Easy 80%, Normal 70%, Hard 60%

---

### Tavern Healing (Constitution)
**Roll:** 5d4 + CON (determines HP recovered)

| CON | Easy | Normal | Hard | Avg Roll | HP Recovered |
|-----|------|--------|------|----------|--------------|
| 30  | ✓    | -      | -    | 42       | ~42 HP       |
| 25  | ✓    | ✓      | -    | 37       | ~37 HP       |
| 20  | ✓    | ✓      | ✓    | 32       | ~32 HP       |
| 18  | ✓    | ✓      | -    | 30       | ~30 HP       |
| 15  | ✓    | ✓      | ✓    | 27       | ~27 HP       |
| 12  | ✓    | ✓      | ✓    | 24       | ~24 HP       |
| 10  | -    | ✓      | -    | 22       | ~22 HP       |
| 6   | ✓    | -      | -    | 18       | ~18 HP       |

**Difference:** Easy (CON 18) recovers **43% more HP** than Hard (CON 12)

---

## Combat Comparison Matrix

### Example: Easy (STR 18, CON 18, DEX 18) vs Hard (STR 12, CON 12, DEX 12)

| Mechanic         | Easy Value | Hard Value | Easy Advantage |
|------------------|------------|------------|----------------|
| HP               | 60         | 36         | **+67%**       |
| AC (plate)       | 31         | 28         | **+11%**       |
| Attack Bonus     | +18        | +12        | **+50%**       |
| Hit % (AC 20)    | 70%        | 50%        | **+40%**       |
| Hit % (AC 25)    | 45%        | 25%        | **+80%**       |
| Flee % (DEX 15)  | 80%        | 60%        | **+33%**       |
| Divine Success   | 85%        | 50%        | **+70%**       |
| Listen Success   | 85%        | 50%        | **+70%**       |
| Revival (1st)    | 100%       | 85%        | **+18%**       |
| Revival (2nd)    | 85%        | 50%        | **+70%**       |
| Starting Gold    | 140g       | 120g       | **+17%**       |
| Tavern Healing   | 30 HP      | 24 HP      | **+25%**       |

**Overall Combat Power:** Easy is approximately **3-4× more effective** than Hard

---

## Equipment Affordability (Starting Gold)

| Item           | Cost | Easy Can Buy | Normal Can Buy | Hard Can Buy |
|----------------|------|--------------|----------------|--------------|
| Leather Armor  | 50g  | ✓            | ✓              | ✓            |
| Chain Mail     | 150g | ✓            | Maybe          | No           |
| Plate Armor    | 300g | No*          | No             | No           |
| Basic Weapon   | 50g  | ✓            | ✓              | ✓            |
| Good Weapon    | 100g | ✓            | Maybe          | No           |
| Great Weapon   | 200g | No           | No             | No           |
| Health Potion  | 20g  | ✓ (×5)       | ✓ (×3)         | ✓ (×2)       |
| Mana Potion    | 30g  | ✓ (×3)       | ✓ (×2)         | ✓ (×1)       |

*Can buy with high CHA roll or low-HP bonus

**Starting Loadout Examples:**

**Easy (180g):**
- Chain Mail (150g)
- Good Weapon (100g) → 250g needed, or...
- Leather (50g) + Good Weapon (100g) + 3 Potions (60g) = 210g ✗
- Chain Mail (150g) + Basic Weapon (50g) = 200g

**Normal (150g):**
- Leather (50g) + Good Weapon (100g) = 150g ✓
- Chain Mail (150g) + nothing else ✗

**Hard (130g):**
- Leather (50g) + Basic Weapon (50g) + 3 Potions (60g) = 160g ✗
- Leather (50g) + Basic Weapon (50g) + 1 Potion (20g) = 120g ✓

---

## Depth Progression Guide

### Recommended Max Depth by Difficulty

| Character Stats | Easy | Normal | Hard |
|----------------|------|--------|------|
| Below Average (<12 avg) | 15 | 10 | 5 |
| Average (12-15 avg) | 20 | 15 | 10 |
| Above Average (15-18 avg) | 25+ | 20 | 15 |
| Excellent (18+ avg) | 30+ | 25+ | 20 |

**Depth Milestones:**
- **Depth 1-5:** Tutorial, low-risk
- **Depth 6-10:** Moderate challenge begins
- **Depth 11-15:** Significant difficulty spike
- **Depth 16-20:** High risk, high reward
- **Depth 21+:** Extreme danger, endgame content

---

## Death Probability by Depth

| Depth Range | Easy | Normal | Hard | Relative Risk |
|-------------|------|--------|------|---------------|
| 1-5         | 5%   | 10%    | 20%  | Hard: 4× Easy |
| 6-10        | 15%  | 30%    | 50%  | Hard: 3.3× Easy |
| 11-15       | 30%  | 55%    | 80%  | Hard: 2.7× Easy |
| 16-20       | 50%  | 80%    | 95%  | Hard: 1.9× Easy |
| 21+         | 70%  | 95%    | 99%+ | Hard: 1.4× Easy |

**Interpretation:** 
- Easy: Can reach depth 20+ regularly
- Normal: Reaching depth 15 is an achievement
- Hard: Reaching depth 10 requires perfect play

---

## Resource Consumption Rate

**Per 10 Rooms (average):**

| Resource      | Easy | Normal | Hard | Hard Uses |
|---------------|------|--------|------|-----------|
| HP Lost       | 30   | 60     | 120  | **4× more** |
| Potions Used  | 2    | 4      | 8    | **4× more** |
| Gold Earned   | 150  | 150    | 150  | Same      |
| Gold Spent    | 50   | 100    | 200  | **4× more** |
| Net Gold      | +100 | +50    | -50  | **Negative!** |
| Deaths        | 0.1  | 0.3    | 0.8  | **8× more** |

**Conclusion:** Hard difficulty operates at a **resource deficit** - you spend more than you earn!

---

## Optimal Stat Allocation Priority

### Easy Difficulty
1. Constitution (HP, AC, healing)
2. Strength (damage, hit rate)
3. Wisdom (utility, revival)
4. Charisma (gold bonus)
5. Dexterity (init, flee)
6. Perception (detection)
7. Intelligence (spells, minor)

**Strategy:** Balanced offense + defense, can afford variety

---

### Normal Difficulty
1. Constitution (survival critical)
2. Strength (offense important)
3. Wisdom (revival insurance)
4. Dexterity (flee when needed)
5. Perception (information)
6. Charisma (economy help)
7. Intelligence (luxury)

**Strategy:** Prioritize survival, then damage

---

### Hard Difficulty
1. **Constitution** (HP = life or death)
2. **Wisdom** (revival is mandatory)
3. **Dexterity** (must flee often)
4. Perception (avoid bad fights)
5. Strength (acceptable 10-12)
6. Charisma (dump to 6-8)
7. Intelligence (dump to 4-6)

**Strategy:** Extreme min-max for survival, sacrifice offense/utility

---

## Summary: Key Numbers to Remember

| Metric | Easy | Normal | Hard |
|--------|------|--------|------|
| **Avg HP** | 60 | 48 | 36 |
| **Avg AC** | 28 | 26 | 24 |
| **Avg Attack Bonus** | +18 | +15 | +12 |
| **Avg Gold** | 170 | 150 | 130 |
| **Skill Success** | 75% | 60% | 45% |
| **Revival Success** | 90% | 75% | 60% |
| **Max Safe Depth** | 25+ | 20 | 15 |
| **Overall Power** | 4× | 2× | 1× |

---

**Quick Reference Version 1.0**  
**Last Updated:** October 31, 2025
