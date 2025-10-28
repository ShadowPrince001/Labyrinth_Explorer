from game.__main__ import dungeon_run
from game.entities import Character

# Create a test character with stable attributes
c = Character(name='Tester', clazz='Adventurer', max_hp=30, gold=100)
c.attributes = {'Strength':12,'Dexterity':12,'Constitution':12,'Intelligence':10,'Wisdom':10,'Charisma':10,'Perception':10}
c.max_hp = 30
c.hp = 30

# Monkeypatch input to select '2' (return to town) after first room navigation prompt
import builtins
orig_input = builtins.input
inputs = iter(['1','2'])  # choose 'Go deeper' then 'Return to town' to force a single room run
builtins.input = lambda prompt='': next(inputs, '2')
try:
    dungeon_run(c)
finally:
    builtins.input = orig_input
print('debug_dungeon_order completed')
