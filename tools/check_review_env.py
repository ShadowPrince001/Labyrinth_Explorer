"""Quick check for review-related environment variables.

Run: python tools/check_review_env.py

Exits non-zero and prints a clear message if any required variables are missing.
"""

from __future__ import annotations

import os
import sys


REQUIRED = [
    "GITHUB_TOKEN",
    "GITHUB_REPO",
]


def main() -> int:
    missing = []
    for k in REQUIRED:
        v = os.getenv(k)
        if not v:
            missing.append(k)
    if missing:
        print("Missing required environment variables:")
        for k in missing:
            print(f" - {k}")
        print(
            "Configure these as repository secrets/variables or in your hosting platform's environment settings."
        )
        return 2
    print("All required review env variables are present.")
    optional = {
        "GITHUB_REVIEWS_PATH": os.getenv("GITHUB_REVIEWS_PATH", "reviews"),
        "GITHUB_REVIEWS_BRANCH": os.getenv("GITHUB_REVIEWS_BRANCH", "(repo default)"),
    }
    for k, v in optional.items():
        print(f"{k} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
