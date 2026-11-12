"""Launch one version of the AI Escape Room.

Usage:
    python run.py v2
    python run.py v1
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI Escape Room.")
    parser.add_argument(
        "version",
        nargs="?",
        default="v2",
        choices=["v1", "v2"],
        help="Game version to launch (default: v2)",
    )
    args = parser.parse_args()
    if args.version == "v1":
        from app_v1 import main as run_v1

        run_v1()
    else:
        from app_v2 import main as run_v2

        run_v2()


if __name__ == "__main__":
    main()
