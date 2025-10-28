"""Smoke tests for miscellaneous helpers: combat utilities and potion/spell menus.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import builtins
import random
from game.entities import Character, Monster, Weapon, Armor
from game import combat

class InputQueue:
    def __init__(self, responses):
        self.responses = responses
    def __call__(self, prompt=""):
        if self.responses:
            v = self.responses.pop(0)
            print(prompt + v)
            return v
        print(prompt)
        return ""


def make_char():
    c = Character(name="Tester", clazz="Fighter", max_hp=40, gold=50)
    c.hp = 30
    c.attributes = {"Strength":14, "Dexterity":12, "Constitution":13, "Intelligence":10, "Wisdom":10, "Charisma":8, "Perception":10}
    return c


def run():
    random.seed(42)
    char = make_char()
    print("== compute_armor_class (no armor) ==")
    print(combat.compute_armor_class(char, ac_bonus=0))

    print("== compute_armor_class (with armor undamaged) ==")
    char.armor = Armor(name="Chain", armor_class=14, damaged=False)
    print(combat.compute_armor_class(char))

    print("== compute_armor_class (with armor damaged) ==")
    char.armor.damaged = True
    print(combat.compute_armor_class(char))

    print("== choose_weapon ==")
    char.weapons.append(Weapon(name="Shortsword", damage_die="1d8"))
    char.weapons.append(Weapon(name="Mace", damage_die="1d6"))
    # choose second weapon via input
    builtins.input = InputQueue(["2"]) 
    w = combat.choose_weapon(char)
    print(f"Chosen weapon: {w.name}")

    print("== examine_monster ==")
    m = Monster(name="Goblin", hp=8, armor_class=12, damage_die="1d6")
    combat.examine_monster(char, m)

    print("== use_potion (no potions) ==")
    res = combat.use_potion(char, {})
    print("use_potion returned:", res)

    print("== use_potion (with potions) ==")
    char.potion_uses = {"Healing": 1}
    builtins.input = InputQueue(["1"])  # choose healing
    res = combat.use_potion(char, {})
    print("use_potion returned:", res)

    print("other_flow_test completed")

if __name__ == '__main__':
    run()
