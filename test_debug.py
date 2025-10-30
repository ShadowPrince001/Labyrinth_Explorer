"""Quick test to verify debug output is visible"""

import sys

print("=" * 60)
print("🧪 TEST: If you can see this, debug output is working!")
sys.stdout.flush()

print("🧪 TEST: Testing multiple lines...")
sys.stdout.flush()

print("🧪 TEST: Python version:", sys.version)
sys.stdout.flush()

print("🧪 TEST: Done!")
print("=" * 60)
sys.stdout.flush()
