import os, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from game.entities import Character, Weapon
from game.shop import sell_items


class E:
    def __init__(self):
        self.events = []

    def __call__(self, e):
        print("EVT:", e)
        self.events.append(e)


def chooser(prompt: str) -> str:
    print("PROMPT:", prompt, end="")
    return input()


def main():
    c = Character(name="X", clazz="Y", max_hp=10, gold=100)
    c.weapons.append(Weapon(name="Dagger", damage_die="1d4"))
    weapons_data = [{"name": "Dagger", "price": 40}]
    armors_data = []
    potions_data = []
    sell_items(c, weapons_data, armors_data, potions_data, emitter=E(), chooser=chooser)


if __name__ == "__main__":
    main()
