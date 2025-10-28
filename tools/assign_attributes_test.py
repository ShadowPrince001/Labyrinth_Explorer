"""Test assign_attributes flow by simulating choices."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import builtins
from game.__main__ import assign_attributes

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

# Simulate always choosing the first remaining attribute
builtins.input = InputQueue(["1"] * 10)
attrs = assign_attributes()
print("Assigned attributes:", attrs)
