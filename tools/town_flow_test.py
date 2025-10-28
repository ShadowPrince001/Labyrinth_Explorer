"""Automated, non-interactive smoke test for town menu flows.
This script fabricates a Character and walks through town functions with canned inputs.
"""
import sys
import os
import random
import builtins

# Ensure repo root is on sys.path so "import game" works when running this script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.entities import Character, Weapon, Armor, MagicItem
from game import town

# Simple input queue helper
class InputQueue:
    def __init__(self, responses):
        self.responses = responses
    def __call__(self, prompt=""):
        if self.responses:
            val = self.responses.pop(0)
            print(prompt + val)
            return val
        print(prompt)
        return ""


def make_test_char():
    c = Character(name="Test", clazz="Adventurer", max_hp=30, gold=100)
    c.hp = 20
    c.attributes = {"Strength": 12, "Dexterity": 12, "Constitution": 12, "Intelligence": 10, "Wisdom": 10, "Charisma": 10, "Perception": 10}
    # Add a damaged weapon and armor for weaponsmith
    c.weapons.append(Weapon(name="Rusty Sword", damage_die="1d6", damaged=True))
    c.armors_owned.append(Armor(name="Old Mail", armor_class=12, damaged=True))
    c.armor = None
    c.magic_items.append(MagicItem(name="Cursed Ring", type="ring", effect="strange", cursed=True))
    return c


def run_tests():
    char = make_test_char()
    print("== healer ==")
    town.healer(char)
    print(char.hp, char.max_hp)

    print("== eat_meal ==")
    town.eat_meal(char)
    print(char.hp)

    print("== tavern_drink ==")
    random.seed(1)
    town.tavern_drink(char)

    print("== gambling invalid bet ==")
    builtins.input = InputQueue(["3"])  # invalid (less than 5)
    town.gambling(char)

    print("== gambling valid bet ==")
    builtins.input = InputQueue(["5"])  # minimal valid bet
    random.seed(2)
    town.gambling(char)

    print("== praying ==")
    town.praying(char)

    print("== donate invalid ==")
    builtins.input = InputQueue(["abc"])  # invalid number
    town.donate(char)

    print("== donate valid ==")
    builtins.input = InputQueue(["10"])  # donate 10
    town.donate(char)

    print("== side_quests accept then back ==")
    # Accept a quest then back from side_quests
    builtins.input = InputQueue(["1", "y", "3"])  # ask, accept, back
    town.side_quests(char)

    print("== train back and then train buy ==")
    builtins.input = InputQueue([str(len(char.attributes)+1), "1"])  # Back then pick first attr
    town.train(char)

    print("== rest ==")
    town.rest(char)

    print("== companion_menu rename then back ==")
    builtins.input = InputQueue(["1", "Buddy", "3"])  # rename then back
    town.companion_menu(char)

    print("== weaponsmith repair and back ==")
    # Choose first damaged item (1), confirm auto-repair costs 20 (we have gold)
    builtins.input = InputQueue(["1"]) 
    town.weaponsmith(char)

    print("== remove_curses remove then back ==")
    builtins.input = InputQueue(["1"])  # remove the cursed ring
    town.remove_curses(char)

    print("All town flow tests completed.")


if __name__ == '__main__':
    run_tests()
