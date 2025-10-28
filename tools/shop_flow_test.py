"""Smoke test that navigates the shop categories and returns.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.entities import Character
from game import shop
import builtins

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
    c = Character(name="Shopper", clazz="Adventurer", max_hp=10, gold=200)
    c.attributes = {"Strength":10, "Dexterity":10, "Constitution":10, "Intelligence":10, "Wisdom":10, "Charisma":10, "Perception":10}
    return c


def run():
    char = make_char()
    # Sequence: open shop -> browse weapons -> back -> browse armor -> back -> spells -> back -> leave
    builtins.input = InputQueue(["1", "1", "1", "2", "1", "3", "1", "6"]) 
    shop.open_shop(char)
    print("shop_flow_test completed")

if __name__ == '__main__':
    run()
