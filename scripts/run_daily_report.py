from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from src.daily_report import send_report
    send_report()


if __name__ == "__main__":
    main()
