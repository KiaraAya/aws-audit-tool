# ---------------------------------------------------------
# main.py
# Single-command entry point for aws-audit-tool
# ---------------------------------------------------------

from __future__ import annotations

# Imports -----------------------------------------------

import logging
from config import Settings
from runner import run_all

# Logging -----------------------------------------------

# Configure logging for the entire application
def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

# Entry Point -------------------------------------------

# The main function serves as the single entry point for the aws-audit-tool
def main() -> None:
    _configure_logging()

    s = Settings()
    out_dir = run_all(s)
    print(f"Run completed. Outputs at: {out_dir}")

# Script Guard ------------------------------------------

# The script guard ensures that main() is only executed when this file is run directly
if __name__ == "__main__":
    main()
