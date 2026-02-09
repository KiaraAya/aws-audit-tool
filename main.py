# main.py
"""
Single-command entry point for aws-audit-tool.

Usage:
    python main.py

Configuration is read from environment variables via Settings.
"""

from __future__ import annotations

import logging
from config import Settings
from runner import run_all


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    _configure_logging()

    s = Settings()          # regions come from AWS_AUDIT_REGIONS or default in config.py
    out_dir = run_all(s)
    print(f"Run completed. Outputs at: {out_dir}")


if __name__ == "__main__":
    main()
