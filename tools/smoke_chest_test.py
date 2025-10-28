from game.labyrinth import generate_room

for i in range(100):
    r = generate_room(1)
    if r.has_chest:
        print('Chest:', r.chest_magic_item)
