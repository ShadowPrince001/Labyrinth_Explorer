"""Test buying a weapon and selling it back via the shop flows."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.entities import Character
from game import shop
from game.data_loader import load_weapons
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
    c = Character(name="Buyer", clazz="Adventurer", max_hp=10, gold=500)
    c.attributes = {"Strength":10, "Dexterity":10, "Constitution":10, "Intelligence":10, "Wisdom":10, "Charisma":10, "Perception":10}
    return c


def run():
    char = make_char()
    # Determine the menu index for the first purchasable weapon dynamically.
    weapons = [w for w in load_weapons() if int(w.get('price', 0)) > 0]
    if not weapons:
        print("No weapons data available; skipping shop purchase/sell test")
        return
    # In the browse_weapons menu, menu_index starts at 2 (1 is Back)
    first_weapon_menu_index = 2

    # Sequence: open shop -> select Weapons (1) -> choose first weapon -> back to main (1)
    # -> Sell items (5) -> choose first sellable (2) -> confirm (y) -> Leave (6)
    # Note: weapon/armor/potion menus reserve '1' for Back; sell menu also reserves '1' for Back
    inputs = ["1", str(first_weapon_menu_index), "1", "5", "2", "y", "6"]
    builtins.input = InputQueue(inputs)
    shop.open_shop(char)
    print("shop_purchase_sell_test completed")


if __name__ == '__main__':
    run()
