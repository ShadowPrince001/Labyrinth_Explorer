#!/usr/bin/env python3
"""
Batch runner: Executes 1000 simulations for each difficulty (easy, normal, hard)
and generates a comprehensive Markdown analysis plus JSON summaries.

Outputs:
- SIMULATION_ANALYSIS_1000_RUNS.md (root)
- tools/output/results_<difficulty>.json (raw per-run metrics)
- tools/output/summary_<difficulty>.json (aggregated stats)

Run:
  python tools/run_difficulty_batches.py
"""
import os
import sys
import json
import math
from statistics import mean, median
from collections import Counter, defaultdict
from typing import List, Dict, Any

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from simulate_runs_FIXED import run_simulation, SimulationMetrics  # type: ignore


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return float(min(values))
    if p >= 100:
        return float(max(values))
    vs = sorted(values)
    k = (len(vs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(vs[int(k)])
    d0 = vs[f] * (c - k)
    d1 = vs[c] * (k - f)
    return float(d0 + d1)


def to_jsonable(metrics: SimulationMetrics) -> Dict[str, Any]:
    return {
        "character_name": metrics.character_name,
        "starting_stats": metrics.starting_stats,
        "won_game": metrics.won_game,
        "permanent_death": metrics.permanent_death,
        "total_turns": metrics.total_turns,
        "total_encounters": metrics.total_encounters,
        "dragon_encountered": metrics.dragon_encountered,
        "max_depth_reached": metrics.max_depth_reached,
        "final_gold": metrics.final_gold,
        "total_attacks": metrics.total_attacks,
        "attacks_hit": metrics.attacks_hit,
        "attacks_missed": metrics.attacks_missed,
        "attacks_blocked": metrics.attacks_blocked,
        "critical_hits": metrics.critical_hits,
        "damage_dealt": metrics.damage_dealt,
        "damage_taken": metrics.damage_taken,
        "monsters_killed": metrics.monsters_killed,
        "deaths": metrics.deaths,
        "revivals": metrics.revivals,
        "divine_used": metrics.divine_used,
        "divine_success": metrics.divine_success,
        "examine_used": metrics.examine_used,
        "potions_used": metrics.potions_used,
        "spells_cast": metrics.spells_cast,
        "gold_earned": metrics.gold_earned,
        "gold_spent_weapons": metrics.gold_spent_weapons,
        "gold_spent_armor": metrics.gold_spent_armor,
        "gold_spent_potions": metrics.gold_spent_potions,
        "gold_spent_training": metrics.gold_spent_training,
        "weapons_bought": metrics.weapons_bought,
        "armor_bought": metrics.armor_bought,
        "potions_bought": metrics.potions_bought,
        "training_sessions": metrics.training_sessions,
        "stats_trained": dict(metrics.stats_trained),
        "town_visits": metrics.town_visits,
        "death_reasons": dict(metrics.death_reasons),
        "quests_completed": metrics.quests_completed,
        "quest_gold_earned": metrics.quest_gold_earned,
        "final_stats": metrics.final_stats,
        "final_hp": metrics.final_hp,
        "final_max_hp": metrics.final_max_hp,
        "hit_rate": metrics.hit_rate(),
        "divine_success_rate": metrics.divine_success_rate(),
        "avg_damage_per_encounter": metrics.avg_damage_per_encounter(),
    }


def compute_summary(results: List[SimulationMetrics]) -> Dict[str, Any]:
    total = len(results)
    victories = [r for r in results if r.won_game]
    deaths = [r for r in results if r.permanent_death]

    encounters = [r.total_encounters for r in results]
    turns = [r.total_turns for r in results]
    depths = [r.max_depth_reached for r in results]
    deaths_per = [r.deaths for r in results]
    revivals_per = [r.revivals for r in results]
    hit_rates = [r.hit_rate() for r in results if r.total_attacks > 0]
    potions_used = [r.potions_used for r in results]

    total_attacks = sum(r.total_attacks for r in results)
    total_hits = sum(r.attacks_hit for r in results)
    total_misses = sum(r.attacks_missed for r in results)
    total_blocked = sum(r.attacks_blocked for r in results)

    total_kills = sum(r.monsters_killed for r in results)
    total_damage_dealt = sum(r.damage_dealt for r in results)
    total_damage_taken = sum(r.damage_taken for r in results)

    total_gold_earned = sum(r.gold_earned for r in results)
    spent_weapons = sum(r.gold_spent_weapons for r in results)
    spent_armor = sum(r.gold_spent_armor for r in results)
    spent_potions = sum(r.gold_spent_potions for r in results)
    spent_training = sum(r.gold_spent_training for r in results)

    # Depth histogram
    depth_hist = dict(Counter(depths))

    # Death reasons top 10
    death_reasons = defaultdict(int)
    for r in results:
        for k, v in getattr(r, "death_reasons", {}).items():
            death_reasons[k] += v
    top_death_reasons = sorted(
        death_reasons.items(), key=lambda kv: kv[1], reverse=True
    )[:10]

    # Training distribution
    training_dist = defaultdict(int)
    for r in results:
        for attr, count in getattr(r, "stats_trained", {}).items():
            training_dist[attr] += count

    # Starting/final stat averages (subset of key stats)
    def avg_stat(rs, key):
        vals = [r.starting_stats.get(key, 10) for r in rs]
        return sum(vals) / len(vals) if vals else 0.0

    def avg_final_stat(rs, key):
        vals = [r.final_stats.get(key, 10) for r in rs]
        return sum(vals) / len(vals) if vals else 0.0

    vict = victories if victories else results

    summary = {
        "total": total,
        "victories": len(victories),
        "victory_rate": len(victories) / total if total else 0,
        "permanent_deaths": len(deaths),
        "dragon_encounter_rate": (
            sum(1 for r in results if r.dragon_encountered) / total if total else 0
        ),
        "encounters": {
            "sum": sum(encounters),
            "mean": mean(encounters) if encounters else 0,
            "median": median(encounters) if encounters else 0,
            "p90": percentile(encounters, 90),
            "p99": percentile(encounters, 99),
        },
        "turns": {
            "sum": sum(turns),
            "mean": mean(turns) if turns else 0,
            "median": median(turns) if turns else 0,
            "p90": percentile(turns, 90),
            "p99": percentile(turns, 99),
        },
        "max_depth": {
            "mean": mean(depths) if depths else 0,
            "median": median(depths) if depths else 0,
            "histogram": depth_hist,
            "max": max(depths) if depths else 0,
        },
        "deaths_per_char": {
            "mean": mean(deaths_per) if deaths_per else 0,
            "median": median(deaths_per) if deaths_per else 0,
            "p90": percentile(deaths_per, 90),
        },
        "revivals_per_char": {
            "mean": mean(revivals_per) if revivals_per else 0,
            "median": median(revivals_per) if revivals_per else 0,
            "p90": percentile(revivals_per, 90),
        },
        "hit_rates": {
            "mean": mean(hit_rates) if hit_rates else 0,
            "median": median(hit_rates) if hit_rates else 0,
            "p90": percentile(hit_rates, 90) if hit_rates else 0,
        },
        "potions_used_per_char": {
            "mean": mean(potions_used) if potions_used else 0,
            "median": median(potions_used) if potions_used else 0,
            "p90": percentile(potions_used, 90),
        },
        "combat": {
            "attacks": total_attacks,
            "hits": total_hits,
            "misses": total_misses,
            "blocked": total_blocked,
            "hit_pct": (total_hits / total_attacks) if total_attacks else 0,
            "kills": total_kills,
            "avg_turns_per_kill": (total_attacks / total_kills) if total_kills else 0,
            "damage_dealt": total_damage_dealt,
            "damage_taken": total_damage_taken,
            "avg_dealt_per_encounter": (
                (total_damage_dealt / sum(encounters)) if sum(encounters) else 0
            ),
            "avg_taken_per_encounter": (
                (total_damage_taken / sum(encounters)) if sum(encounters) else 0
            ),
        },
        "economy": {
            "gold_earned_total": total_gold_earned,
            "gold_earned_mean": (total_gold_earned / total) if total else 0,
            "spent_weapons": spent_weapons,
            "spent_armor": spent_armor,
            "spent_potions": spent_potions,
            "spent_training": spent_training,
            "spent_total": spent_weapons + spent_armor + spent_potions + spent_training,
        },
        "death_reasons_top": top_death_reasons,
        "training_distribution": dict(training_dist),
        "victory_insights": {
            "avg_start_STR": avg_stat(vict, "Strength"),
            "avg_start_CON": avg_stat(vict, "Constitution"),
            "avg_final_STR": avg_final_stat(vict, "Strength"),
            "avg_final_CON": avg_final_stat(vict, "Constitution"),
            "avg_encounters_to_victory": (
                mean([r.total_encounters for r in vict]) if vict else 0
            ),
            "avg_gold_at_victory": mean([r.final_gold for r in vict]) if vict else 0,
        },
    }
    return summary


def write_markdown(aggregate: Dict[str, Any], path_md: str):
    lines = []
    lines.append("# 1000-run Simulation Analysis (Easy → Normal → Hard)\n")
    lines.append("Generated by tools/run_difficulty_batches.py\n")

    for difficulty in ["easy", "normal", "hard"]:
        s = aggregate[difficulty]["summary"]
        lines.append(f"\n## {difficulty.title()}\n")
        lines.append(
            f"- Victory rate: {s['victory_rate']*100:.1f}% ({s['victories']}/{s['total']})\n"
        )
        lines.append(
            f"- Dragon encounter rate: {s['dragon_encounter_rate']*100:.1f}%\n"
        )
        lines.append("\n### Progression\n")
        lines.append(
            f"Encounters — mean {s['encounters']['mean']:.2f}, median {s['encounters']['median']:.0f}, p90 {s['encounters']['p90']:.0f}, p99 {s['encounters']['p99']:.0f}\n"
        )
        lines.append(
            f"Turns — mean {s['turns']['mean']:.1f}, median {s['turns']['median']:.0f}, p90 {s['turns']['p90']:.0f}, p99 {s['turns']['p99']:.0f}\n"
        )
        lines.append(
            f"Max depth — mean {s['max_depth']['mean']:.2f}, median {s['max_depth']['median']:.0f}, max {s['max_depth']['max']}\n"
        )
        # Depth histogram compact table
        dh = s["max_depth"]["histogram"] or {}
        if dh:
            depth_keys = sorted(dh.keys())
            depth_row = ", ".join([f"{k}: {dh[k]}" for k in depth_keys])
            lines.append(f"Depth histogram: {depth_row}\n")

        lines.append("\n### Combat\n")
        lines.append(
            f"Hit rate: {s['combat']['hit_pct']*100:.1f}% — Attacks {s['combat']['attacks']:,}, Hits {s['combat']['hits']:,}, Misses {s['combat']['misses']:,}, Blocked {s['combat']['blocked']:,}\n"
        )
        lines.append(
            f"Kills: {s['combat']['kills']:,}; Avg turns per kill: {s['combat']['avg_turns_per_kill']:.2f}\n"
        )
        lines.append(
            f"Damage per encounter — dealt {s['combat']['avg_dealt_per_encounter']:.1f}, taken {s['combat']['avg_taken_per_encounter']:.1f}\n"
        )

        lines.append("\n### Survivability\n")
        lines.append(
            f"Deaths per character — mean {s['deaths_per_char']['mean']:.2f}, median {s['deaths_per_char']['median']:.0f}, p90 {s['deaths_per_char']['p90']:.0f}\n"
        )
        lines.append(
            f"Revivals per character — mean {s['revivals_per_char']['mean']:.2f}, median {s['revivals_per_char']['median']:.0f}, p90 {s['revivals_per_char']['p90']:.0f}\n"
        )
        if s["death_reasons_top"]:
            top = ", ".join([f"{name}: {cnt}" for name, cnt in s["death_reasons_top"]])
            lines.append(f"Top death reasons: {top}\n")

        lines.append("\n### Consumables & Abilities\n")
        lines.append(
            f"Potions used per character — mean {s['potions_used_per_char']['mean']:.2f}, median {s['potions_used_per_char']['median']:.0f}, p90 {s['potions_used_per_char']['p90']:.0f}\n"
        )
        lines.append(
            f"Hit rates (per character) — mean {s['hit_rates']['mean']:.1f}%, median {s['hit_rates']['median']:.1f}%, p90 {s['hit_rates']['p90']:.1f}%\n"
        )

        lines.append("\n### Economy\n")
        lines.append(
            f"Gold earned — total {s['economy']['gold_earned_total']:,}g; mean per character {s['economy']['gold_earned_mean']:.0f}g\n"
        )
        lines.append(
            f"Gold spent — weapons {s['economy']['spent_weapons']:,}g, armor {s['economy']['spent_armor']:,}g, potions {s['economy']['spent_potions']:,}g, training {s['economy']['spent_training']:,}g (total {s['economy']['spent_total']:,}g)\n"
        )

        lines.append("\n### Training\n")
        if s["training_distribution"]:
            td = s["training_distribution"]
            order = [
                "Strength",
                "Constitution",
                "Dexterity",
                "Wisdom",
                "Intelligence",
                "Charisma",
                "Perception",
            ]
            row = ", ".join([f"{k}: {td.get(k, 0)}" for k in order])
            lines.append(f"Training distribution: {row}\n")
        else:
            lines.append("No training recorded.\n")

        lines.append("\n### Victory insights\n")
        vi = s["victory_insights"]
        lines.append(
            f"Avg starting STR {vi['avg_start_STR']:.1f}, CON {vi['avg_start_CON']:.1f}; Avg final STR {vi['avg_final_STR']:.1f}, CON {vi['avg_final_CON']:.1f}\n"
        )
        lines.append(
            f"Avg encounters to victory {vi['avg_encounters_to_victory']:.1f}; Avg gold at victory {vi['avg_gold_at_victory']:.0f}g\n"
        )

    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(os.path.join(ROOT, "tools", "output"), exist_ok=True)
    aggregate = {}

    for difficulty in ("easy", "normal", "hard"):
        results = run_simulation(1000, difficulty=difficulty, verbose=False)
        # Save raw metrics
        json_path = os.path.join(ROOT, "tools", "output", f"results_{difficulty}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump([to_jsonable(r) for r in results], f)

        summary = compute_summary(results)
        sum_path = os.path.join(ROOT, "tools", "output", f"summary_{difficulty}.json")
        with open(sum_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        aggregate[difficulty] = {"summary": summary}

    # Write markdown report to project root
    md_path = os.path.join(ROOT, "SIMULATION_ANALYSIS_1000_RUNS.md")
    write_markdown(aggregate, md_path)
    print(f"\nWrote analysis to {md_path}")


if __name__ == "__main__":
    main()
