# Importations ------------------------------------------------------------
import argparse
from config import Settings
from runner import run_all

# CLI entry point ---------------------------------------------------------
def main():
    """
    Main entry point for aws-audit-tool CLI.

    This function parses command-line arguments, initializes
    application settings, and triggers the execution flow.
    """
    
    # Argument parser configuration ---------------------------------------
    parser = argparse.ArgumentParser(prog="aws-audit-tool")
    
    # Subcommands ---------------------------------------------------------
    sub = parser.add_subparsers(dest="cmd", required=True)

    # 'run' command -------------------------------------------------------
    run = sub.add_parser("run", help="Run inventory + cloudmapper")
    run.add_argument("--regions", help="CSV regions override (ex: us-east-1,us-west-2)")
    run.add_argument("--cloudmapper-dir", help="Path to cloudmapper repo")

    # Parse CLI arguments -------------------------------------------------
    args = parser.parse_args()
    
    # Load default settings from environment variables --------------------
    s = Settings()

    # Override regions if provided via CLI --------------------------------
    if args.regions:
        s.regions = [r.strip() for r in args.regions.split(",") if r.strip()]
        
    # Override CloudMapper path if provided via CLI -----------------------
    if args.cloudmapper_dir:
        s.cloudmapper_dir = args.cloudmapper_dir

    # Execute main workflow -----------------------------------------------
    out = run_all(s)
    print(f"Run completed. Outputs at: {out}")

# Script execution guard --------------------------------------------------
if __name__ == "__main__":
    main()
