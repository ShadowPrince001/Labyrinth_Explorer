from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import List, Optional

from .data_loader import load_monsters


@dataclass
class SideQuest:
    id: int
    monster_name: str
    quest_type: str  # 'kill' or 'collect'
    goal: int
    progress: int
    reward: int
    desc: str
    completed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "SideQuest":
        return SideQuest(
            id=int(d.get("id", 0)),
            monster_name=str(d.get("monster_name", "Unknown")),
            quest_type=str(d.get("quest_type", "kill")),
            goal=int(d.get("goal", 1)),
            progress=int(d.get("progress", 0)),
            reward=int(d.get("reward", 0)),
            desc=str(d.get("desc", d.get("description", ""))),
            completed=bool(d.get("completed", False)),
        )


class QuestManager:
    """Manages generation and progression of side quests.

    Quests are stored on the Character as a list of plain dicts so they
    remain serializable with the existing save format. QuestManager
    provides helpers to generate, check kills, and turn-in quests.
    """

    def __init__(self):
        self._next_id = 1

    def _make_quest_for_monster(self, m: dict) -> SideQuest:
        # Flavor can vary, but mechanics are always: kill 1 of the target monster
        # Keep quest_type for text variety, but force goal=1
        qtype = "kill" if random.random() < 0.6 else "collect"
        goal = 1
        # Reward formula: scale with difficulty and inverse of wander_chance
        wander = float(m.get("wander_chance", m.get("wanderChance", 0.02)) or 0.02)
        difficulty = int(m.get("difficulty", m.get("difficulty", 1)))
        # Avoid division by zero and keep rewards reasonable
        reward = int(difficulty * 20 + (1.0 / max(wander, 0.01)) // 2)
        desc = f"{'Slay' if qtype == 'kill' else 'Collect parts from'} {m.get('name')} ({goal})"
        q = SideQuest(
            id=self._next_id,
            monster_name=m.get("name"),
            quest_type=qtype,
            goal=goal,
            progress=0,
            reward=reward,
            desc=desc,
        )
        self._next_id += 1
        return q

    def _load_existing(self, character) -> List[SideQuest]:
        qs = []
        for q in getattr(character, "side_quests", []) or []:
            if isinstance(q, SideQuest):
                qs.append(q)
            elif isinstance(q, dict):
                try:
                    qs.append(SideQuest.from_dict(q))
                except Exception:
                    # Fallback for legacy format
                    qs.append(
                        SideQuest(
                            id=self._next_id,
                            monster_name=str(q.get("desc", "Unknown")),
                            quest_type="kill",
                            goal=1,
                            progress=0,
                            reward=int(q.get("reward", 0)),
                            desc=str(q.get("desc", "Unknown")),
                            completed=bool(q.get("completed", False)),
                        )
                    )
                    self._next_id += 1
        return qs

    def _save_back(self, character, quests: List[SideQuest]) -> None:
        # Persist as list of dicts for compatibility with save system
        character.side_quests = [q.to_dict() for q in quests]

    def generate_up_to(self, character, limit: int = 3) -> List[SideQuest]:
        """Generate new quests up to `limit` total active quests on the character."""
        existing = self._load_existing(character)
        # If already at or above limit, do nothing
        if len(existing) >= limit:
            return existing
        # Choose monsters with wander_chance > 0.02
        mons = [
            m
            for m in load_monsters()
            if float(m.get("wander_chance", m.get("wanderChance", 0))) > 0.02
        ]
        if not mons:
            return existing
        # Pick distinct monsters not already used in existing quests when possible
        candidates = [
            m for m in mons if m.get("name") not in [q.monster_name for q in existing]
        ]
        random.shuffle(candidates)
        to_create = min(limit - len(existing), len(candidates))
        for i in range(to_create):
            q = self._make_quest_for_monster(candidates[i])
            existing.append(q)
        self._save_back(character, existing)
        return existing

    def ask_for_new_quests(self, character, n: int = 3) -> List[SideQuest]:
        """Public interface to ask the town for new quests. Returns the new active list."""
        return self.generate_up_to(character, limit=n)

    def check_kill(self, character, monster) -> List[SideQuest]:
        """Call when a monster is killed to update any relevant quests.

        Returns the list of quests that changed state (marked completed).
        """
        changed = []
        quests = self._load_existing(character)
        name = getattr(monster, "name", str(monster))
        # Iterate and collect indices to remove after awarding rewards
        to_remove = []
        for i, q in enumerate(quests):
            if q.completed:
                continue
            if q.monster_name == name:
                # Any successful kill of the quest's monster completes the quest
                q.progress = max(q.progress, q.goal)
                if q.progress >= q.goal:
                    # Auto-turn-in: award reward and mark for removal
                    try:
                        character.gold += int(q.reward)
                    except Exception:
                        try:
                            character.gold += int(getattr(q, "reward", 0))
                        except Exception:
                            pass
                    changed.append(q)
                    to_remove.append(i)
        # Remove completed quests (highest indices first)
        for idx in sorted(to_remove, reverse=True):
            try:
                quests.pop(idx)
            except Exception:
                pass
        # Persist updated quest list
        if changed:
            self._save_back(character, quests)
        return changed

    def turn_in(self, character, quest_id: int) -> Optional[SideQuest]:
        quests = self._load_existing(character)
        for q in quests:
            if q.id == int(quest_id) and q.completed:
                character.gold += q.reward
                quests.remove(q)
                self._save_back(character, quests)
                return q
        return None


# Module-level singleton manager for convenience
quest_manager = QuestManager()
