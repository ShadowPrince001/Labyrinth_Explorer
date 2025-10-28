import random
from typing import Tuple


def parse_die(notation: str) -> Tuple[int, int]:
	# format NdM, e.g., 2d6
	n_str, d_str = notation.lower().split('d')
	num = int(n_str)
	sides = int(d_str)
	return num, sides


def roll(notation: str) -> int:
	num, sides = parse_die(notation)
	return sum(random.randint(1, sides) for _ in range(num))


def roll_d20() -> int:
	return random.randint(1, 20)


def roll_damage(die: str) -> int:
	return roll(die)
